import re
import html
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

def clean_input_url(raw: str) -> str:
    u = raw.strip().replace(',', '').strip()
    return u.split('?')[0].split('&')[0]

# --- 1. INSTAGRAM ENGINE (Multi-Layer Bypass) ---
def get_instagram_data(url: str):
    clean = clean_input_url(url)
    m = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean)
    if not m:
        return None
    shortcode = m.group(1)

    # Method A: Fast VxInstagram Metadata API
    try:
        vx_url = f"https://api.vxinstagram.com/reel/{shortcode}"
        r = requests.get(vx_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            data = r.json()
            video_url = data.get("video_url") or data.get("url")
            if video_url:
                return {
                    "title": f"Instagram Reel - {shortcode}",
                    "download_url": video_url,
                    "thumbnail": data.get("thumbnail_url") or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Method B: Direct Instagram Open Graph Scraper
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(f"https://www.instagram.com/reel/{shortcode}/embed/captioned/", headers=headers, timeout=7)
        if res.status_code == 200:
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', res.text) or re.findall(r'"video_url":"([^"]+)"', res.text)
            if v_matches:
                v_clean = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                return {
                    "title": f"Instagram Reel - {shortcode}",
                    "download_url": v_clean,
                    "thumbnail": f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- 2. FACEBOOK ENGINE ---
def get_facebook_data(url: str):
    clean = clean_input_url(url)
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr={clean}", timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                return {
                    "title": d.get("title") or "Facebook Video",
                    "download_url": v,
                    "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Facebook+Video",
                    "platform": "Facebook"
                }
    except Exception:
        pass
    return None

# --- 3. YOUTUBE ENGINE ---
def get_youtube_data(url: str):
    clean = clean_input_url(url)
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', clean)
    if not m:
        return None
    video_id = m.group(1)

    hosts = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de", "https://invidious.protokolla.fi"]
    for h in hosts:
        try:
            r = requests.get(f"{h}/api/v1/videos/{video_id}", timeout=6)
            if r.status_code == 200:
                streams = r.json().get("formatStreams", [])
                if streams:
                    return {
                        "title": r.json().get("title", "YouTube Video"),
                        "download_url": streams[-1].get("url"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "platform": "YouTube"
                    }
        except Exception:
            continue
    return None

# --- 4. TIKTOK & UNIVERSAL ENGINE ---
def get_universal_data(url: str):
    nodes = ["https://api.cobalt.tools", "https://cobalt-api.kwiatekm.tokyo", "https://api.server.ovh/cobalt"]
    for node in nodes:
        try:
            r = requests.post(node, json={"url": url.strip().replace(',', ''), "videoQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=7)
            if r.status_code == 200:
                d = r.json()
                if d.get("url"):
                    return {
                        "title": d.get("filename") or "Social Media Video",
                        "download_url": d.get("url"),
                        "thumbnail": "https://via.placeholder.com/640x360?text=Video+Ready",
                        "platform": "Social Media"
                    }
        except Exception:
            continue
    return None

# --- MAIN ROUTE ---
@app.post("/download")
def extract_video(req: VideoRequest):
    raw_url = req.url.strip()

    if "instagram.com" in raw_url:
        res = get_instagram_data(raw_url)
        if res:
            return {"status": "success", "data": res}

    if "facebook.com" in raw_url or "fb.watch" in raw_url:
        res = get_facebook_data(raw_url)
        if res:
            return {"status": "success", "data": res}

    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        res = get_youtube_data(raw_url)
        if res:
            return {"status": "success", "data": res}

    res = get_universal_data(raw_url)
    if res:
        return {"status": "success", "data": res}

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure the link is public and valid.")

# --- DIRECT STREAM (No Corrupted Files) ---
@app.get("/stream")
def stream_video(video_url: str, title: str = "video"):
    try:
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:35] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=20)
        return StreamingResponse(
            res.iter_content(chunk_size=1024 * 512),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_title}.mp4"'
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Stream download failed.")
