import os
import sys
import json
import socket
import subprocess
import threading
import re

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
ARCHIVE_FILE = os.path.join(BASE_DIR, "archive.txt")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# yt-dlp command: use the Python module to ensure correct version
YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]

# Add deno to PATH if installed in user profile
_deno_path = os.path.join(os.path.expanduser("~"), ".deno", "bin")
if os.path.isdir(_deno_path) and _deno_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _deno_path + os.pathsep + os.environ.get("PATH", "")

# --- Global download state ---
download_state = {
    "active": False,
    "current": 0,
    "total": 0,
    "tracks": {},
}
state_lock = threading.Lock()
stop_event = threading.Event()
current_proc = None  # reference to the running yt-dlp subprocess


# --- Models ---
class PlaylistRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    tracks: list
    format: str = "mp3"
    quality: str = "320k"
    metadata: bool = True


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/playlist")
async def get_playlist(req: PlaylistRequest):
    try:
        result = subprocess.run(
            [*YTDLP_CMD, "--flat-playlist", "--dump-json", req.url],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "Failed to fetch playlist"}

        tracks = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            thumbnails = data.get("thumbnails") or []
            thumbnail = thumbnails[-1].get("url", "") if thumbnails else ""
            tracks.append({
                "id": data.get("id", ""),
                "title": data.get("title", "Unknown"),
                "duration": data.get("duration") or 0,
                "thumbnail": thumbnail,
                "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
            })
        return {"tracks": tracks}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: la playlist est trop grande ou problème réseau"}
    except Exception as e:
        return {"error": str(e)}


def download_worker(tracks, fmt, quality, metadata):
    format_map = {
        "mp3": ["-x", "--audio-format", "mp3", "--audio-quality", quality],
        "flac": ["-x", "--audio-format", "flac"],
        "opus": ["-x", "--audio-format", "opus"],
        "m4a": ["-x", "--audio-format", "m4a", "--audio-quality", quality],
        "mp4": ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]", "--merge-output-format", "mp4"],
    }

    fmt_args = format_map.get(fmt, format_map["mp3"])

    global current_proc
    stop_event.clear()

    with state_lock:
        download_state["active"] = True
        download_state["current"] = 0
        download_state["total"] = len(tracks)
        download_state["tracks"] = {
            t["id"]: {"status": "waiting", "progress": 0, "filename": "", "error": ""}
            for t in tracks
        }

    for track in tracks:
        if stop_event.is_set():
            break

        tid = track["id"]
        with state_lock:
            download_state["tracks"][tid]["status"] = "downloading"

        cmd = [
            *YTDLP_CMD,
            "--newline",
            "--download-archive", ARCHIVE_FILE,
            "-o", os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            *fmt_args,
        ]
        if metadata:
            cmd.extend(["--embed-metadata", "--embed-thumbnail"])
        cmd.append(track["url"])

        try:
            print(f"[DL] {track['title']} -> {' '.join(cmd[-1:])}")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            with state_lock:
                current_proc = proc
            last_error = ""
            for line in proc.stdout:
                if stop_event.is_set():
                    proc.terminate()
                    break
                line = line.strip()
                if line.startswith("ERROR"):
                    last_error = line
                match = re.search(r"\[download\]\s+([\d.]+)%", line)
                if match:
                    with state_lock:
                        download_state["tracks"][tid]["progress"] = float(match.group(1))
                        download_state["tracks"][tid]["status"] = "downloading"
                if "[ExtractAudio]" in line or "[Merger]" in line:
                    with state_lock:
                        download_state["tracks"][tid]["status"] = "converting"
                if "has already been recorded in the archive" in line:
                    with state_lock:
                        download_state["tracks"][tid]["status"] = "done"
                        download_state["tracks"][tid]["progress"] = 100
                dest_match = re.search(r"\[(?:Merger|ExtractAudio|download)\] Destination: (.+)", line)
                if dest_match:
                    with state_lock:
                        download_state["tracks"][tid]["filename"] = os.path.basename(dest_match.group(1))

            proc.wait()

            with state_lock:
                current_proc = None
                if stop_event.is_set():
                    download_state["tracks"][tid]["status"] = "error"
                    download_state["tracks"][tid]["error"] = "Arrêté"
                elif download_state["tracks"][tid]["status"] != "done":
                    if proc.returncode == 0:
                        download_state["tracks"][tid]["status"] = "done"
                        download_state["tracks"][tid]["progress"] = 100
                    else:
                        download_state["tracks"][tid]["status"] = "error"
                        download_state["tracks"][tid]["error"] = last_error or "Échec du téléchargement"
                        print(f"[ERR] {track['title']}: {last_error}")
                download_state["current"] += 1

        except Exception as e:
            with state_lock:
                current_proc = None
                download_state["tracks"][tid]["status"] = "error"
                download_state["tracks"][tid]["error"] = str(e)
                download_state["current"] += 1

    # Mark remaining waiting tracks as cancelled if stopped
    if stop_event.is_set():
        with state_lock:
            for tid, info in download_state["tracks"].items():
                if info["status"] == "waiting":
                    info["status"] = "error"
                    info["error"] = "Arrêté"

    with state_lock:
        download_state["active"] = False


@app.post("/api/stop")
async def stop_download():
    global current_proc
    stop_event.set()
    with state_lock:
        if current_proc:
            current_proc.terminate()
    return {"status": "stopping"}


@app.post("/api/reset")
async def reset_state():
    stop_event.clear()
    with state_lock:
        download_state["active"] = False
        download_state["current"] = 0
        download_state["total"] = 0
        download_state["tracks"] = {}
    return {"status": "reset"}


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    with state_lock:
        if download_state["active"]:
            return {"error": "Un téléchargement est déjà en cours"}

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
        return {"error": "Fichier introuvable"}
    return FileResponse(filepath, filename=filename)


# --- Startup ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"\n  YouTube Downloader")
    print(f"  Local:   http://localhost:8000")
    print(f"  Mobile:  http://{ip}:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
