<?php
// existingSeriesFetcher.php

// Set response type to JSON
header("Content-Type: application/json");

// -----------------------------------------------------------------------------
// Step 1: Read and validate input from client
// -----------------------------------------------------------------------------

$rawInput = file_get_contents("php://input");
$input = json_decode($rawInput, true);

// Validate that input is a valid JSON object
if (!is_array($input)) {
    http_response_code(400);
    echo json_encode(["status" => "error", "message" => "Invalid JSON input"]);
    exit;
}

// Extract and sanitize required fields
$serverUrl = rtrim($input["url"] ?? "", "/");
$authToken = $input["authToken"] ?? "";
$librariesList = $input["libraries"] ?? [];

// Ensure required fields are present
if (!$serverUrl || !$authToken || !$librariesList) {
    http_response_code(400);
    echo json_encode([
        "status" => "error",
        "message" => "Missing required fields: url, authentication token, or libraries list"
    ]);
    exit;
}

// -----------------------------------------------------------------------------
// Helper Functions for ASIN Logic
// -----------------------------------------------------------------------------

$asinCacheFile = __DIR__ . '/../asin_cache.json';
$asinCache = [];
if (file_exists($asinCacheFile)) {
    $loaded = json_decode(file_get_contents($asinCacheFile), true);
    if (is_array($loaded)) {
        $asinCache = $loaded;
    }
}

function saveASINCache()
{
    global $asinCache, $asinCacheFile;
    // Attempt to save; suppress errors if permissions deny it
    @file_put_contents($asinCacheFile, json_encode($asinCache));
}

function getASINFromAudible($title, $author)
{
    global $asinCache;

    if (!$title)
        return null;

    $cacheKey = "$title|$author";
    if (array_key_exists($cacheKey, $asinCache)) {
        return $asinCache[$cacheKey];
    }

    $query = $title . " " . $author;
    $encodedQuery = urlencode($query);
    $url = "https://www.audible.de/search?keywords=$encodedQuery";

    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT => 5,
        CURLOPT_USERAGENT => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ]);

    // Polite delay
    usleep(500000); // 0.5s

    $html = curl_exec($ch);
    $error = curl_error($ch);
    curl_close($ch);

    if ($html === false) {
        // Network error
        return null;
    }

    // Simple regex to find data-asin="B0..."
    // Matches: data-asin="B00..."
    if (preg_match('/data-asin="(B0[A-Z0-9]{8})"/', $html, $matches)) {
        $asin = $matches[1];
        $asinCache[$cacheKey] = $asin;
        saveASINCache();
        return $asin;
    }
    else {
        $asinCache[$cacheKey] = null; // Cache failure too
        return null;
    }
}

function updateASINInABS($serverUrl, $token, $itemId, $asin)
{
    $url = "$serverUrl/api/items/$itemId/media";
    $data = [
        "metadata" => [
            "asin" => $asin
        ]
    ];
    $jsonData = json_encode($data);

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => "PATCH",
        CURLOPT_POSTFIELDS => $jsonData,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => [
            "Authorization: Bearer $token",
            "Content-Type: application/json",
            "Content-Length: " . strlen($jsonData)
        ],
        CURLOPT_TIMEOUT => 5
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    // 200-299 success
    return ($httpCode >= 200 && $httpCode < 300);
}

// -----------------------------------------------------------------------------
// Step 2: Fetch all series with pagination
// -----------------------------------------------------------------------------

$seriesFirstASIN = [];
$seriesAllASIN = [];

$limit = 20;

foreach ($librariesList as $library) {
    $libraryId = $library["id"] ?? null;
    if (!$libraryId)
        continue;

    $page = 0;
    $totalSeriesCount = null;

    do {
        $seriesUrl = "$serverUrl/api/libraries/$libraryId/series?limit=$limit&page=$page";

        $seriesCurl = curl_init($seriesUrl);
        curl_setopt_array($seriesCurl, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ["Authorization: Bearer $authToken"]
        ]);

        $seriesResponse = curl_exec($seriesCurl);
        $seriesStatus = curl_getinfo($seriesCurl, CURLINFO_HTTP_CODE);
        curl_close($seriesCurl);

        if ($seriesStatus < 200 || $seriesStatus >= 300) {
            http_response_code($seriesStatus);
            echo json_encode([
                "status" => "error",
                "message" => "Failed to fetch series (page $page) from library $libraryId",
                "details" => $seriesResponse
            ]);
            exit;
        }

        $seriesData = json_decode($seriesResponse, true);
        $seriesList = $seriesData["results"] ?? [];

        if ($totalSeriesCount === null && isset($seriesData["total"])) {
            $totalSeriesCount = $seriesData["total"];
        }

        foreach ($seriesList as $series) {
            $seriesName = $series["name"] ?? "Unknown Series";
            $books = $series["books"] ?? [];

            // -----------------------------------------------------------------
            // ASIN Fix / Write-back logic for all books in this series
            // -----------------------------------------------------------------
            foreach ($books as &$bookRef) {
                // Using reference &$bookRef so we can update it if needed 
                // (though we mainly need to update $meta for local use)

                $meta = $bookRef["media"]["metadata"] ?? [];
                $asin = $meta["asin"] ?? null;
                $title = $meta["title"] ?? "";
                $author = $meta["authorName"] ?? "";
                $itemId = $bookRef["id"] ?? null;

                if (!$asin && $title) {
                    // Try to find ASIN
                    $fetchedAsin = getASINFromAudible($title, $author);
                    if ($fetchedAsin) {
                        $asin = $fetchedAsin;
                        // Update local object for response
                        $bookRef["media"]["metadata"]["asin"] = $asin;

                        // Write back to ABS
                        if ($itemId) {
                            updateASINInABS($serverUrl, $authToken, $itemId, $asin);
                        }
                    }
                }
            }
            unset($bookRef); // break reference

            // Now process for response (using potentially updated ASINs)
            if (!empty($books)) {
                $firstMeta = $books[0]["media"]["metadata"] ?? [];
                $seriesFirstASIN[] = [
                    "series" => $seriesName,
                    "title" => $firstMeta["title"] ?? "Unknown Title",
                    "asin" => $firstMeta["asin"] ?? "Unknown ASIN"
                ];
            }

            foreach ($books as $book) {
                $meta = $book["media"]["metadata"] ?? [];
                $bookSeriesName = $meta["seriesName"] ?? "Unknown Series";
                $bookHashPosition = strpos($bookSeriesName, "#");
                $bookSeriesPosition = ($bookHashPosition !== false)
                    ? trim(substr($bookSeriesName, $bookHashPosition + 1))
                    : "N/A";
                $seriesAllASIN[] = [
                    "series" => $seriesName,
                    "title" => $meta["title"] ?? "Unknown Title",
                    "asin" => $meta["asin"] ?? "Unknown ASIN",
                    "subtitle" => $meta["subtitle"] ?? "No Subtitle",
                    "seriesPosition" => $bookSeriesPosition
                ];
            }
        }

        $page++;
    } while (count($seriesFirstASIN) < $totalSeriesCount);
}

// -----------------------------------------------------------------------------
// Step 3: Respond with structured result
// -----------------------------------------------------------------------------

echo json_encode([
    "status" => "success",
    "seriesFirstASIN" => $seriesFirstASIN,
    "seriesAllASIN" => $seriesAllASIN
]);