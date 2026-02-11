# 📘 Complete Your Collection - Audiobookshelf Edition

**Identify missing audiobooks from the series you own.**  
_Designed for use with Audible series and Audiobookshelf._

Live demo: [completeseries.lily-pad.uk](https://completeseries.lily-pad.uk)

---

## 🚀 Quick Start (Recommended for Local Audiobookshelf)

The easiest way to run this application with full features (including automatic ASIN fixes and CORS handling) is using the included **Python Proxy**.

### Prerequisites
- Python 3 installed on your system.
- An Audiobookshelf server (local or remote).

### Installation & Usage

1.  **Download/Clone** this repository.
2.  Open a terminal in the folder.
3.  Make the start script executable (Linux/Mac):
    ```bash
    chmod +x start.sh
    ```
4.  **Start the application:**
    ```bash
    ./start.sh
    ```
5.  Open your browser at: [http://localhost:8000](http://localhost:8000)

---

## ✨ New Features

### 🔍 Auto-ASIN Discovery & Fix (Self-Healing)
If your Audiobookshelf library has books without ASINs (Audible IDs), the app ordinarily can't check for missing parts.
**Now:**
- The app automatically **searches Audible** for missing ASINs based on Title/Author.
- It **saves the found ASIN back to your Audiobookshelf server** automatically.
- This ensures your library metadata gets better with every scan!

### 🟢 Spotify Integration
Missing a book?
- Every missing book card now has a **Spotify icon**.
- Click it to instantly search for that book on Spotify.

### 📜 "Show All Series" Mode
Want to verify your complete series too?
- Go to **Settings** (Gear Icon).
- Check **"Show ALL series (including complete ones)"**.
- This allows you to audit your entire library, not just the incomplete parts.

---

## 🔧 Core Features

- **Secure Connection**: Connects to your Audiobookshelf server using a local proxy to bypass CORS issues securely.
- **Smart Filtering**: Automatically identifies missing books in Audible series.
- **Privacy Focused**: Credentials are saved only in your browser's *Local Storage*. No data is sent to any third-party server except `audimeta.de` (for metadata) and your own Audiobookshelf.
- **Region Support**: UK, US, CA, AU, FR, DE, JP, IT, IN, ES, BR.
- **Export Data**: Download your missing book list as **CSV** or **JSON** for external use.
- **Ignore/Hide**: Permanently hide books or series you don't care about.

---

## 🧪 Detailed Usage Guide

1.  **Login**:
    - Enter your Audiobookshelf URL (e.g., `http://192.168.1.50:13378`).
    - Enter Username/Password OR use an API Key (Toggle in Advanced Settings).
    - *Tip: If you use the Python Proxy (`./start.sh`), connection issues are rare.*

2.  **Select Library**:
    - Choose the library you want to scan (e.g., "Audiobooks").

3.  **Scan & Review**:
    - The app will fetch your books and compare them with the official Audible series lists.
    - **Missing books** appear in the main view.
    - **Complete series** are hidden unless you enable "Show All Series".

4.  **Fixing Metadata (Important!)**:
    - If you see "0 Series Missing" but know you have gaps, your books might lack ASINs.
    - Just run the scan! The app will now **auto-detect** and **auto-fix** these missing ASINs in the background.

5.  **Exporting**:
    - Use the menu (top left) to **Export Missing (CSV/JSON)**.

---

## 🛠️ Advanced Development (Building from Source)

If you want to modify the frontend code or build the production bundle yourself (requires Node.js 18+):

1.  **Install Dependencies**:
    ```bash
    npm install
    ```
2.  **Build Production Bundle (`dist/`)**:
    ```bash
    npm run build
    ```
3.  **Run Development Server**:
    ```bash
    npm run serve:all
    ```

---

## 📄 License
MIT – Use it, improve it, share it.
