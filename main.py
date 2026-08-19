import re
import html
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Dikol Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

def clean_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    u = raw_url.strip().rstrip(',').rstrip('/')
    u = u.split('?')[0].split('&')[0]
    return u

# --- 1. INSTAGRAM ENGINE ---
def extract_instagram(raw_url: str):
    clean = clean_url(raw_url)
    match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean)
    if not match:
        return None
    shortcode = match.group(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 314.0.0.19.108",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": "936619743392459"
    }

    # Method A: Instagram Embed Extraction
    try:
        embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
        res = requests.get(embed_url, headers=headers, timeout=8)
        if res.status_code == 200:
            html_text = res.text
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', html_text) or re.findall(r'"video_url":"([^"]+)"', html_text)
            if v_matches:
                video_url = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                t_matches = re.findall(r'display_url\\":\\"([^"\\]+)', html_text)
                thumb = html.unescape(t_matches[0].replace('\\u0026', '&').replace('\\/', '/')) if t_matches else ""
                return {
                    "title": f"Instagram Reel - {shortcode}",
                    "download_url": video_url,
                    "thumbnail": thumb or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Method B: Dedicated Scraper Gateway
    try:
        gw_url = f"https://api.vkrdownloader.com/server?vkr=https://www.instagram.com/reel/{shortcode}/"
        r = requests.get(gw_url, timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                return {
                    "title": d.get("title") or f"Instagram Reel - {shortcode}",
                    "download_url": v,
                    "thumbnail": d.get("thumbnail") or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- 2. YOUTUBE / SHORTS ENGINE ---
def extract_youtube(raw_url: str):
    clean = clean_url(raw_url)
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', clean)
    if not m:
        return None
    video_id = m.group(1)

    hosts = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de", "https://invidious.protokolla.fi"]
    for host in hosts:
        try:
            r = requests.get(f"{host}/api/v1/videos/{video_id}", timeout=6)
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

# --- 3. FACEBOOK & TIKTOK ENGINE ---
def extract_universal(raw_url: str):
    clean = raw_url.strip().rstrip(',')
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr={clean}", timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                platform = "Social Media"
                if "facebook.com" in clean or "fb.watch" in clean:
                    platform = "Facebook"
                elif "tiktok.com" in clean:
                    platform = "TikTok"

                return {
                    "title": d.get("title") or f"{platform} Video",
                    "download_url": v,
                    "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Video+Ready",
                    "platform": platform
                }
    except Exception:
        pass
    return None

# --- MAIN API ROUTE ---
@app.post("/download")
def download_api(req: VideoRequest):
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Please enter a valid URL.")

    # 1. Instagram
    if "instagram.com" in raw_url:
        insta = extract_instagram(raw_url)
        if insta:
            return {"status": "success", "data": insta}

    # 2. YouTube
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        yt = extract_youtube(raw_url)
        if yt:
            return {"status": "success", "data": yt}

    # 3. Facebook, TikTok & Universal
    universal = extract_universal(raw_url)
    if universal:
        return {"status": "success", "data": universal}

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure the link is public and valid.")

# --- PROXY STREAM ROUTE ---
@app.get("/stream")
def stream_media(video_url: str = Query(...), title: str = Query("video")):
    try:
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:35] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=25)
        return StreamingResponse(
            res.iter_content(chunk_size=1024 * 512),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_title}.mp4"'
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Stream failed.")
