# YouTube Playlist Downloader

Download entire YouTube playlists directly to your Android phone via a mobile-first web interface.

## Features

- 🎵 **Playlist Import** — Add any YouTube playlist and download all tracks at once
- 📱 **Mobile-First** — Responsive design optimized for Android phones
- ⚙️ **Granular Control** — Choose format (MP3, FLAC, OPUS, M4A, MP4), audio quality, metadata
- ✅ **Track Selection** — Pick individual tracks or select all at once
- ⏸️ **Stop Downloads** — Pause any download in progress
- 📥 **Auto-Save** — Files automatically save to your phone's Downloads folder
- 🚀 **Lightweight** — No bloat, just FastAPI + yt-dlp + vanilla HTML/CSS/JS

## Requirements

- **Windows PC** with Python 3.10+
- **FFmpeg** (for audio conversion) — [download here](https://ffmpeg.org/download.html)
- **Same Wi-Fi network** — Your PC and Android phone must be on the same network

## Installation

1. **Clone or download this project**

```bash
git clone <repository-url>
cd "YouTube Downloader"
```

2. **Install Python dependencies**

```bash
pip install -r requirements.txt
```

3. **Verify ffmpeg is installed**

```bash
ffmpeg -version
```

If ffmpeg is not found, download it and add it to your system PATH.

## Usage

### Step 1: Start the Server

On your Windows PC, open a terminal in the project folder and run:

```bash
py server.py
```

You'll see output like:

```
  YouTube Downloader
  Local:   http://localhost:8000
  Mobile:  http://192.168.1.84:8000
```

**Keep this window open while downloading.**

### Step 2: Access from Your Phone

On your Android phone, open your browser and visit the **Mobile** URL shown above.

Example: `http://192.168.1.84:8000`

### Step 3: Download a Playlist

1. Paste a YouTube playlist URL into the text field
2. Click **"Charger"** (Load)
3. Select the tracks you want to download
4. Configure settings if needed (format, quality, metadata)
5. Click **"Télécharger la sélection"** (Download Selection)
6. Files automatically save to your phone's Downloads folder

## Settings

| Setting | Options | Default |
|---------|---------|---------|
| **Format** | MP3, FLAC, OPUS, M4A, MP4 | MP3 |
| **Quality** | 128k, 192k, 256k, 320k | 320k |
| **Metadata** | On/Off | On (embeds title, artist, cover) |

## File Location

- **On PC**: `YouTube Downloader/downloads/`
- **On Phone**: Files save to the Downloads folder (via browser)

## Tips

- 🎧 For best audio quality, choose **MP3 at 320k** or **FLAC**
- ⚡ Smaller files load faster on mobile — try **128k or 192k** for streaming
- 🔒 This only works on your local Wi-Fi network (no internet required once setup)
- 📶 To access from anywhere (4G), use [Tailscale](https://tailscale.com) to create a secure VPN

## Troubleshooting

### "A download is already in progress"

Restart the server:
1. Press `Ctrl + C` in the terminal
2. Run `py server.py` again

### Playlist won't load

- Check your internet connection
- Verify the URL is a valid YouTube playlist
- Make sure yt-dlp can access YouTube

### Files not downloading to phone

- Confirm both devices are on the **same Wi-Fi network**
- Try refreshing the page in your browser
- Check your phone's Downloads folder

## Performance Notes

- Large playlists (100+ tracks) may take time to load
- Downloads happen sequentially (one track at a time)
- Internet speed affects download time
- FFmpeg conversion adds a few seconds per track

## License

Free to use. Built with FastAPI, yt-dlp, and vanilla JavaScript.

## Support

For issues or suggestions, check the project repository or refer to [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp).
