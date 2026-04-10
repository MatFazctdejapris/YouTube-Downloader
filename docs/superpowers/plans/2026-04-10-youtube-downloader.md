# YouTube Playlist Downloader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first web interface + Python backend to download YouTube playlists via yt-dlp, accessible from an Android phone on the same Wi-Fi network.

**Architecture:** Single FastAPI server (`server.py`) serves a standalone HTML file (`index.html`) and exposes REST endpoints that wrap yt-dlp commands. Downloads are stored locally and served as static files for the phone to fetch.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, yt-dlp, ffmpeg

---

## File Structure

| File | Responsibility |
|---|---|
| `server.py` | FastAPI app: API endpoints, yt-dlp subprocess calls, file serving, progress tracking |
| `index.html` | Complete UI: HTML + inline CSS + inline JS. Mobile-first dark mode. |
| `requirements.txt` | Python dependencies |
| `downloads/` | Created at runtime, stores downloaded files |
| `archive.txt` | Created at runtime by yt-dlp `--download-archive`, tracks already-downloaded videos |

---

### Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
yt-dlp==2024.12.23
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 3: Verify yt-dlp and ffmpeg are available**

Run: `yt-dlp --version && ffmpeg -version`
Expected: Both print version info. If ffmpeg is missing, user must install it separately.

---

### Task 2: Server Core — App Setup & Static File Serving

**Files:**
- Create: `server.py`

- [ ] **Step 1: Create server.py with app setup and index.html serving**

```python
import os
import socket
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
ARCHIVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive.txt")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"\n  YouTube Downloader running at:")
    print(f"  Local:   http://localhost:8000")
    print(f"  Mobile:  http://{ip}:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 2: Create a minimal index.html placeholder**

```html
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>YT Downloader</title></head>
<body><h1>YouTube Downloader</h1><p>Server is running.</p></body>
</html>
```

- [ ] **Step 3: Test that the server starts and serves the page**

Run: `python server.py`
Expected: Terminal shows local and mobile URLs. Visiting `http://localhost:8000` in browser shows "YouTube Downloader" heading.

- [ ] **Step 4: Stop the server (Ctrl+C)**

---

### Task 3: API — Playlist Fetching Endpoint

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add the playlist extraction endpoint**

Add these imports at the top of `server.py`:

```python
import subprocess
import json
from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import Optional
```

Add these models and endpoint after the `serve_index` function:

```python
class PlaylistRequest(BaseModel):
    url: str


@app.post("/api/playlist")
async def get_playlist(req: PlaylistRequest):
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                req.url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "Failed to fetch playlist"}

        tracks = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            tracks.append({
                "id": data.get("id", ""),
                "title": data.get("title", "Unknown"),
                "duration": data.get("duration") or 0,
                "thumbnail": data.get("thumbnails", [{}])[-1].get("url", "") if data.get("thumbnails") else "",
                "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
            })
        return {"tracks": tracks}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: playlist too large or network issue"}
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 2: Test the endpoint**

Run: `python server.py` (in background)
Then in another terminal:
```bash
curl -X POST http://localhost:8000/api/playlist -H "Content-Type: application/json" -d "{\"url\": \"https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf\"}"
```
Expected: JSON response with array of tracks containing id, title, duration, thumbnail.

---

### Task 4: API — Download Endpoint with Progress Tracking

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add download state and models**

Add at the top of `server.py`, after the existing imports:

```python
import threading
import re
import time
```

Add after `ARCHIVE_FILE` definition:

```python
# Global download state
download_state = {
    "active": False,
    "current": 0,
    "total": 0,
    "tracks": {},  # id -> {status, progress, filename, error}
}
state_lock = threading.Lock()
```

- [ ] **Step 2: Add the download worker function**

Add after `download_state`:

```python
def download_worker(tracks, fmt, quality, metadata):
    format_map = {
        "mp3": {"ext": "mp3", "args": ["-x", "--audio-format", "mp3", "--audio-quality", quality]},
        "flac": {"ext": "flac", "args": ["-x", "--audio-format", "flac"]},
        "opus": {"ext": "opus", "args": ["-x", "--audio-format", "opus"]},
        "m4a": {"ext": "m4a", "args": ["-x", "--audio-format", "m4a", "--audio-quality", quality]},
        "mp4": {"ext": "mp4", "args": ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]", "--merge-output-format", "mp4"]},
    }

    fmt_config = format_map.get(fmt, format_map["mp3"])

    with state_lock:
        download_state["active"] = True
        download_state["current"] = 0
        download_state["total"] = len(tracks)
        download_state["tracks"] = {
            t["id"]: {"status": "waiting", "progress": 0, "filename": "", "error": ""}
            for t in tracks
        }

    for track in tracks:
        tid = track["id"]
        with state_lock:
            download_state["tracks"][tid]["status"] = "downloading"

        cmd = [
            "yt-dlp",
            "--newline",
            "--download-archive", ARCHIVE_FILE,
            "-o", os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            *fmt_config["args"],
        ]

        if metadata:
            cmd.extend(["--embed-metadata", "--embed-thumbnail"])

        cmd.append(track["url"])

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                line = line.strip()
                # Parse progress from yt-dlp output like "[download]  45.2% of ..."
                match = re.search(r"\[download\]\s+([\d.]+)%", line)
                if match:
                    with state_lock:
                        download_state["tracks"][tid]["progress"] = float(match.group(1))
                        download_state["tracks"][tid]["status"] = "downloading"
                # Detect conversion
                if "[ExtractAudio]" in line or "[Merger]" in line:
                    with state_lock:
                        download_state["tracks"][tid]["status"] = "converting"
                # Detect already downloaded
                if "has already been recorded in the archive" in line:
                    with state_lock:
                        download_state["tracks"][tid]["status"] = "done"
                        download_state["tracks"][tid]["progress"] = 100
                # Detect destination filename
                dest_match = re.search(r"\[(?:Merger|ExtractAudio|download)\] Destination: (.+)", line)
                if dest_match:
                    download_state["tracks"][tid]["filename"] = os.path.basename(dest_match.group(1))

            proc.wait()

            with state_lock:
                if download_state["tracks"][tid]["status"] != "done":
                    if proc.returncode == 0:
                        download_state["tracks"][tid]["status"] = "done"
                        download_state["tracks"][tid]["progress"] = 100
                    else:
                        download_state["tracks"][tid]["status"] = "error"
                        download_state["tracks"][tid]["error"] = "Download failed"
                download_state["current"] += 1

        except Exception as e:
            with state_lock:
                download_state["tracks"][tid]["status"] = "error"
                download_state["tracks"][tid]["error"] = str(e)
                download_state["current"] += 1

    with state_lock:
        download_state["active"] = False
```

- [ ] **Step 3: Add download and status endpoints**

Add after `download_worker`:

```python
class DownloadRequest(BaseModel):
    tracks: list  # [{id, title, url}, ...]
    format: str = "mp3"
    quality: str = "320k"
    metadata: bool = True


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    with state_lock:
        if download_state["active"]:
            return {"error": "A download is already in progress"}

    quality = req.quality.replace("k", "")
    thread = threading.Thread(
        target=download_worker,
        args=(req.tracks, req.format, quality, req.metadata),
        daemon=True,
    )
    thread.start()
    return {"status": "started", "total": len(req.tracks)}


@app.get("/api/status")
async def get_status():
    with state_lock:
        return {
            "active": download_state["active"],
            "current": download_state["current"],
            "total": download_state["total"],
            "tracks": dict(download_state["tracks"]),
        }
```

- [ ] **Step 4: Test download with a single video**

Run the server then:
```bash
curl -X POST http://localhost:8000/api/download -H "Content-Type: application/json" -d "{\"tracks\": [{\"id\": \"dQw4w9WgXcQ\", \"title\": \"Test\", \"url\": \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\"}], \"format\": \"mp3\", \"quality\": \"320k\", \"metadata\": true}"
```
Then check status:
```bash
curl http://localhost:8000/api/status
```
Expected: Status shows progress, eventually `done`. File appears in `downloads/`.

---

### Task 5: API — File Listing & Serving

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add file listing and serving endpoints**

Add after the `get_status` endpoint:

```python
@app.get("/api/files")
async def list_files():
    if not os.path.exists(DOWNLOAD_DIR):
        return {"files": []}
    files = []
    for name in sorted(os.listdir(DOWNLOAD_DIR)):
        filepath = os.path.join(DOWNLOAD_DIR, name)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            files.append({
                "name": name,
                "size": size,
                "size_mb": round(size / (1024 * 1024), 1),
                "url": f"/api/files/{name}",
            })
    return {"files": files}


@app.get("/api/files/{filename:path}")
async def serve_file(filename: str):
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.isfile(filepath):
        return {"error": "File not found"}
    return FileResponse(filepath, filename=filename)
```

- [ ] **Step 2: Test file listing**

After a download completes:
```bash
curl http://localhost:8000/api/files
```
Expected: JSON list of files with name, size, url.

---

### Task 6: Frontend — Complete index.html

**Files:**
- Rewrite: `index.html`

- [ ] **Step 1: Write the complete index.html**

Write the full `index.html` with all 5 zones described in the spec:
- Zone 1: URL input + load button
- Zone 2: Settings accordion (format, quality, metadata)
- Zone 3: Track list with checkboxes, thumbnails, select all/none
- Zone 4: Download progress with per-track bars
- Zone 5: Completed files with individual download buttons

Requirements:
- All CSS inline in `<style>` tag
- All JS inline in `<script>` tag
- Dark mode: background `#1a1a2e`, text `#e0e0e0`, accent `#e94560`
- Mobile-first: large touch targets (min 44px), responsive layout
- Polling `/api/status` every second during active download
- Format duration as `m:ss`
- Show thumbnails in track list
- Accordion for settings, collapsed by default

The HTML file should be fully self-contained with no external dependencies.

---

### Task 7: Integration Test

- [ ] **Step 1: Start the server**

Run: `python server.py`
Expected: Shows local + mobile URLs.

- [ ] **Step 2: Test from browser**

Open `http://localhost:8000` in browser. Verify:
- Page loads with dark theme
- URL input field is visible
- Settings accordion opens/closes

- [ ] **Step 3: Test playlist loading**

Paste a small YouTube playlist URL (2-3 tracks) and click "Charger".
Verify: tracks appear with thumbnails, titles, durations, checkboxes.

- [ ] **Step 4: Test download flow**

Select tracks, click download. Verify:
- Progress bars update in real time
- Status shows downloading → converting → done
- Files appear in "Fichiers prêts" zone
- Download button works (file saves to device)

- [ ] **Step 5: Test from mobile**

Open `http://<PC-IP>:8000` on Android phone. Verify:
- Layout is responsive, buttons are large enough
- Full flow works: load playlist → select → download → save to phone
