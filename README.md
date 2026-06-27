# Hotstar Stream Downloader & Muxer Dashboard

A Flask-based web application and CLI wrapper designed to parse stream manifests, extract media qualities, and orchestrate the downloading/muxing of multi-audio and multi-subtitle streams via **yt-dlp** and **ffmpeg**.

The tool features a glassmorphic dashboard that enables users to paste browser headers or raw XML manifests, analyze available formats, select custom audio/subtitle languages, preview the dynamic `yt-dlp` command, and stream live download logs directly inside the browser.

---

## Key Features

- **Network Headers Parsing**: Reconstructs stream URLs and extracts cookies, User-Agents, and referrer headers directly from pasted network requests (such as Chrome DevTools headers).
- **MPD Manifest Inspection**: Extracts video resolutions, bandwidths, audio languages, and subtitles from raw XML manifests.
- **Interactive Web UI**: Built with a dark glassmorphic design featuring interactive selectors (chips) for video quality, audio languages, and subtitles.
- **Dual Mode Action**:
  - **Mux into MKV**: Merges the selected video track, multiple audio tracks, and subtitles into a single Matroska (`.mkv`) container, enabling multi-audio track selection during playback.
  - **Individual Tracks**: Downloads all selected tracks separately without muxing them.
- **Dynamic Command Generator**: Generates and shows the exact `yt-dlp` shell command in real-time as selectors are toggled. A "Copy Command" button allows users to run it on their own terminal.
- **SSE Terminal Output**: Employs Server-Sent Events (SSE) to run the CLI subprocess in the backend and stream raw console outputs to a simulated web terminal in real-time.

---

## File Structure & Code Breakdown

The project consists of three core components:

```
├── server.py               # Flask application server & XML parser
├── download_hotstar.py     # Command compiler & subprocess execution script
├── templates/
│   └── index.html          # Web UI Dashboard & Client Logic
├── url.txt                 # Temporary cache for pasted header data
└── New Text Document.txt   # (Optional) Fallback offline manifest file
```

### 1. [server.py](file:///C:/Users/batzmods/Desktop/ott%20downloading/hotstar%20testing/server.py)
This is the Flask backend controller handling web endpoints, network requests, XML parsing, and SSE streaming.
- **`parse_mpd(mpd_content)`**: Strips XML namespaces using regex and parses the manifest using Python's standard `xml.etree.ElementTree`. It loops through `AdaptationSet` blocks to discover and sort video qualities (deduplicating by height), audio languages, and subtitle tracks.
- **`@app.route('/analyze')`**: Triggered when headers are pasted. Saves headers to `url.txt`, calls the parse utility from the downloader, and tries to fetch the XML manifest from the reconstructed URL. If direct fetch fails (e.g., due to expired URLs or geo-blocking), it falls back to parsing the contents of `New Text Document.txt` (local manifest).
- **`@app.route('/download')`**: Launches the CLI utility `download_hotstar.py` using Python's `subprocess.Popen` with `-u` (unbuffered output). It reads the program's output line-by-line and streams it to the browser as a `text/event-stream` response.

### 2. [download_hotstar.py](file:///C:/Users/batzmods/Desktop/ott%20downloading/hotstar%20testing/download_hotstar.py)
This script behaves as both a module for the Flask server and a standalone CLI utility.
- **`parse_url_file(filepath)`**: Inspects `url.txt` (which holds raw copy-pasted HTTP headers), extracts request metadata, and reconstructs the target stream URL from HTTP/2 pseudo-headers (e.g., `:scheme`, `:authority`, `:path`) or extracts standard full URLs.
- **`main()`**: Uses `argparse` to process command-line arguments passed by the server:
  - `--quality`: Restricts download to a specific resolution (e.g., `1080p`, `720p`) or grabs the best.
  - `--audio-langs`: Formulates selection commands like `ba[language=hi]+ba[language=en]`.
  - `--sub-langs`: Handles subtitle selection and mapping.
  - `--mode` / `--embed-subs` / `--embed-metadata`: Configures output structure.
- **Command Invocation**: Reassembles the parameters into a full `yt-dlp` executable command including authentication cookies, headers (`User-Agent`, `Referer`, `Origin`), and runs it using `subprocess.run()`.

### 3. [templates/index.html](file:///C:/Users/batzmods/Desktop/ott%20downloading/hotstar%20testing/templates/index.html)
The frontend dashboard built with HTML5, vanilla CSS, and vanilla JavaScript.
- **Design Tokens**: Defined in `:root` with a deep-space glow theme using Outfit and Fira Code fonts, HSL-based transitions, interactive active chips, and glassmorphic card layouts.
- **`updateCommandPreview()`**: Client-side logic that monitors UI toggles and builds a local preview string of the `yt-dlp` CLI command to keep the user informed.
- **`EventSource` Streaming**: Listens to the `/download` stream route. Upon starting a download, it logs output in real-time onto a simulated, auto-scrolling terminal window with color-coded status badges (`Idle`, `Running`, `Completed`, `Failed`).

---

## Installation & Prerequisites

To run this application, make sure your system has the following installed:

1. **Python 3.8+**
2. **Flask**: Install via pip:
   ```bash
   pip install Flask
   ```
3. **yt-dlp**: Make sure `yt-dlp` is installed and updated on your system:
   ```bash
   # On Windows (via winget or manual download)
   winget install yt-dlp
   ```
4. **ffmpeg**: Crucial for muxing and merging streams.
   - Install `ffmpeg` and ensure the binary is added to your system's environment `PATH` variables. Without it, merging video and audio streams into an `.mkv` file will fail.

---

## How to Run & Use

### Step 1: Start the Local Flask Server
Run the backend server using Python:
```bash
python server.py
```
*Note: The server will start on `http://127.0.0.1:5000`.*

### Step 2: Extract Stream Headers
1. Open your browser and navigate to the streaming site.
2. Open **Developer Tools** (`F12`) -> Go to the **Network** tab.
3. Search/Filter for `.mpd` (or `.m3u8` depending on stream type).
4. Select the manifest request, and copy the request headers:
   - *In Chrome/Firefox*: Right-click the request -> **Copy** -> **Copy Request Headers** (or paste the entire response XML directly if you have it).

### Step 3: Analyze and Configure
1. Open `http://127.0.0.1:5000` in your web browser.
2. Paste the headers into the text area and click **Analyze Stream & Get Formats**.
3. Once loaded:
   - Select your preferred **Video Quality** (e.g., 1080p, 720p).
   - Toggle the specific **Audio Languages** and **Subtitle Languages** you want.
   - Choose whether you want to **Mux into MKV** or save them as **Individual Tracks**.
   - Customize the output filename.

### Step 4: Download
- **Copy Command**: Click the copy button to copy the complete `yt-dlp` CLI command (including authenticating cookies) if you want to execute it in your terminal manually.
- **Start Server Download**: Click the launch button to execute the download script directly on your server machine. The output logs will populate the terminal console window in real-time.
