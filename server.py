import http.server
import json
import urllib.request
import urllib.error
import urllib.parse
import sys
import os
import re
import time
from urllib.error import URLError

# Cache for ASIN lookups to speed up subsequent runs
asin_cache_file = "asin_cache.json"
asin_cache = {}

def load_dotenv():
    """Manually load .env file into os.environ to avoid dependencies"""
    env_path = ".env"
    if os.path.exists(env_path):
        print(f"Loading environment from {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                # handle quotes
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ[key.strip()] = value.strip()

# Load env immediately
load_dotenv()

if os.path.exists(asin_cache_file):
    try:
        with open(asin_cache_file, 'r') as f:
            asin_cache = json.load(f)
    except:
        pass

def save_asin_cache():
    try:
        with open(asin_cache_file, 'w') as f:
            json.dump(asin_cache, f)
    except:
        pass

def get_asin_from_audible(title, author):
    """
    Attempts to find an ASIN for a given title/author by searching Audible.de.
    This is a fallback for when Audiobookshelf has no ASIN.
    """
    if not title:
        return None

    cache_key = f"{title}|{author}"
    if cache_key in asin_cache:
        return asin_cache[cache_key]

    try:
        # Construct search query
        query = f"{title} {author}"
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.audible.de/search?keywords={encoded_query}"
        
        # Headers to look like a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        # Polite delay
        time.sleep(0.5) 
        
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            
            # Simple regex to find data-asin="B0..."
            match = re.search(r'data-asin="(B0[A-Z0-9]{8})"', html)
            if match:
                asin = match.group(1)
                print(f"DEBUG: Auto-matched ASIN {asin} for '{title}'")
                asin_cache[cache_key] = asin
                save_asin_cache()
                return asin
            else:
                print(f"DEBUG: No ASIN found on Audible for '{title}'")
                asin_cache[cache_key] = None # Cache failure too
                return None
                
    except Exception as e:
        print(f"DEBUG: Failed to search Audible for '{title}': {e}")
        return None

def update_asin_in_abs(server_url, token, item_id, asin):
    """
    Updates the ASIN for a specific library item in Audiobookshelf.
    """
    try:
        # ABS API Endpoint for updating media: /api/items/{id}/media
        # Removing any trailing slash from server_url just in case
        base_url = server_url.rstrip('/')
        url = f"{base_url}/api/items/{item_id}/media"
        
        # Payload: {"metadata": {"asin": "B0..."}}
        data = {
            "metadata": {
                "asin": asin
            }
        }
        json_data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=json_data, method='PATCH')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if 200 <= response.status < 300:
                print(f"DEBUG: Successfully updated ASIN {asin} for item {item_id} in ABS.")
                return True
            else:
                print(f"DEBUG: ABS update failed with status {response.status}")
                return False

    except Exception as e:
        print(f"DEBUG: Failed to update ASIN in ABS for item {item_id}: {e}")
        return False

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # Route requests based on path
        if self.path.endswith('/php/getLibraries.php'):
            self.handle_get_libraries()
        elif self.path.endswith('/php/existingSeriesFetcher.php'):
            self.handle_existing_series_fetcher()
        else:
            self.send_error(404, "Not Found")
            
    def do_GET(self):
        # Serve static files or handle GET API endpoints
        if self.path == '/api/config':
            self.handle_get_config()
        else:
            # Fallback to SimpleHTTPRequestHandler's default behavior for static files
            super().do_GET()

    def _read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body)

    def _send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_error_response(self, message, status=400, details=None):
        response = {"status": "error", "message": message}
        if details:
            response["details"] = details
        self._send_json_response(response, status)

    def handle_get_config(self):
        """
        Serves public configuration from environment variables.
        ONLY safe variables are exposed.
        """
        try:
            config = {
                "serverUrl": os.environ.get("ABS_URI", ""),
                "apiToken": os.environ.get("ABS_TOKEN", ""),
                "region": os.environ.get("ABS_REGION", "")
            }
            # Only return keys that have values
            response = {k: v for k, v in config.items() if v}
            self._send_json_response(response)
        except Exception as e:
            self._send_error_response(f"Internal server error: {str(e)}", status=500)

    def handle_get_libraries(self):
        try:
            data = self._read_json_body()
            server_url = data.get('url', '').rstrip('/')
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            auth_token = data.get('apiKey', '').strip()
            use_api_key = data.get('useApiKey', False)

            if not server_url:
                return self._send_error_response("Missing required field: url")

            # Step 1: Login if not using API key
            if not use_api_key:
                if not username or not password:
                    return self._send_error_response("Missing username or password")

                login_url = f"{server_url}/login"
                login_payload = json.dumps({"username": username, "password": password}).encode('utf-8')
                req = urllib.request.Request(login_url, data=login_payload, headers={'Content-Type': 'application/json'})
                
                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        login_data = json.load(response)
                        auth_token = login_data.get('user', {}).get('token')
                except urllib.error.HTTPError as e:
                    return self._send_error_response("Login failed", status=e.code, details=e.read().decode('utf-8'))
                except Exception as e:
                    return self._send_error_response(f"Connection error: {str(e)}", status=500)

            if not auth_token:
                return self._send_error_response("Authentication failed or missing token")

            # Step 2: Fetch Libraries
            libraries_url = f"{server_url}/api/libraries"
            req = urllib.request.Request(libraries_url, headers={'Authorization': f'Bearer {auth_token}'})
            
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    libs_data = json.load(response)
            except urllib.error.HTTPError as e:
                return self._send_error_response("Failed to fetch libraries", status=e.code, details=e.read().decode('utf-8'))

            # Step 3: Filter for books
            libraries_list = libs_data.get('libraries', [])
            books_only = [lib for lib in libraries_list if lib.get('mediaType') == 'book']

            self._send_json_response({
                "status": "success",
                "authToken": auth_token,
                "librariesList": books_only
            })

        except Exception as e:
            print(f"DEBUG: Internal server error in handle_get_libraries: {str(e)}")
            import traceback
            traceback.print_exc()
            self._send_error_response(f"Internal server error: {str(e)}", status=500)

    def handle_existing_series_fetcher(self):
        try:
            data = self._read_json_body()
            server_url = data.get('url', '').rstrip('/')
            auth_token = data.get('authToken', '')
            libraries_list = data.get('libraries', [])

            if not server_url or not auth_token:
                return self._send_error_response("Missing url or authToken")

            series_first_asin = []
            series_all_asin = []
            limit = 20

            for library in libraries_list:
                library_id = library.get('id')
                if not library_id:
                    continue

                page = 0
                total_series_count = None

                while True:
                    series_url = f"{server_url}/api/libraries/{library_id}/series?limit={limit}&page={page}"
                    req = urllib.request.Request(series_url, headers={'Authorization': f'Bearer {auth_token}'})

                    try:
                        with urllib.request.urlopen(req) as response:
                            series_data = json.load(response)
                    except urllib.error.HTTPError as e:
                        return self._send_error_response(f"Failed to fetch series page {page}", status=e.code)

                    results = series_data.get('results', [])
                    if total_series_count is None:
                        total_series_count = series_data.get('total', 0)

                    for series in results:
                        series_name = series.get('name', 'Unknown Series')
                        books = series.get('books', [])
                        
                        # DEBUG LOGGING
                        if 'Die Professorin' in series_name:
                            print(f"DEBUG: Detailed dump for '{series_name}':")
                            print(json.dumps(series, indent=2))
                        else:
                            print(f"DEBUG: Found series '{series_name}' with {len(books)} books.")

                        # Statistic counters for this batch
                        valid_asins = 0
                        total_books_batch = 0

                        # First pass: Fix ASINs for all books in this series
                        for book in books:
                            total_books_batch += 1
                            meta = book.get('media', {}).get('metadata', {})
                            asin = meta.get('asin')
                            
                            # Auto-ASIN Lookup if missing
                            if not asin:
                                title = meta.get('title', '')
                                author = meta.get('authorName', '')
                                if title:
                                    fetched_asin = get_asin_from_audible(title, author)
                                    if fetched_asin:
                                        asin = fetched_asin
                                        # Inject back into meta so downstream logic uses it
                                        meta['asin'] = asin

                                        # Save back to ABS if possible
                                        # We need item_id, server_url, auth_token
                                        item_id = book.get('id')
                                        if item_id and server_url and auth_token:
                                            update_asin_in_abs(server_url, auth_token, item_id, asin)

                            if asin:
                                valid_asins += 1
                                
                            # Try to get sequence from metadata first (standard ABS field)
                            # 'sequence' is often a string or number in ABS
                            raw_sequence = book.get('sequence') 
                            
                            # Fallback logic:
                            series_position = "N/A"
                            book_series_name = meta.get('seriesName', 'Unknown Series')

                            if raw_sequence is not None:
                                series_position = str(raw_sequence)
                            elif 'sequence' in meta and meta['sequence'] is not None:
                                series_position = str(meta['sequence'])
                            elif '#' in book_series_name:
                                series_position = book_series_name.split('#')[-1].strip()
                            
                            if 'Die Professorin' in series_name:
                                print(f"DEBUG: Resolved position for '{series_name}' book '{meta.get('title')}': '{series_position}'")
                            
                            series_all_asin.append({
                                "series": series_name,
                                "title": meta.get('title', 'Unknown Title'),
                                "asin": asin if asin else 'Unknown ASIN', # Use the potentially fixed ASIN
                                "subtitle": meta.get('subtitle', 'No Subtitle'),
                                "seriesPosition": series_position
                            })

                        # After processing all books, now we take the first one for the series list
                        # ensuring we have the updated ASIN if it was found.
                        if books:
                            # Use first book's metadata for seriesFirstASIN
                            first_meta = books[0].get('media', {}).get('metadata', {})
                            
                            series_first_asin.append({
                                "series": series_name,
                                "title": first_meta.get('title', 'Unknown Title'),
                                "asin": first_meta.get('asin', 'Unknown ASIN') 
                            })

                    page += 1
                    print(f"DEBUG: Fetched page {page-1}. Valid ASINs in this batch: {valid_asins}/{total_books_batch}")
                    
                    # Break if we have fetched all series or if results in this page were empty/less than limit 
                    # (though checking count vs total is safer as per PHP script logic)
                    if len(results) == 0 or (page * limit >= total_series_count):
                        break

            print(f"DEBUG: Finished fetching. Total Series: {len(series_first_asin)}, Total Books: {len(series_all_asin)}")
            
            self._send_json_response({
                "status": "success",
                "seriesFirstASIN": series_first_asin,
                "seriesAllASIN": series_all_asin
            })

        except Exception as e:
            self._send_error_response(f"Internal server error: {str(e)}", status=500)

class ReusableTCPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        
    print(f"Starting proxy server on port {port}")
    ReusableTCPServer(("", port), ProxyHTTPRequestHandler).serve_forever()
