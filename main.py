import re
import html
import requests
from fastapi import FastAPI, HTTPException
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

# --- ૧. INSTAGRAM DEDICATED ENGINE ---
def extract_instagram_reel(raw_url: str):
    # Regex વડે છેડેથી comma, query parameters બધું જ સાફ કરીને ફક્ત Shortcode ID લેશે
    match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', raw_url)
    if not match:
        return None
    
    shortcode = match.group(1).rstrip(',').strip()
    
    # Gateway A: InstaFix API (100% Direct MP4 CDN)
    try:
        r = requests.get(f"https://ddinstagram.com/api/reel/{shortcode}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            data = r.json()
            if data.get("video_url") or data.get("url"):
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": data.get("video_url") or data.get("url"),
                    "thumbnail": data.get("thumbnail_url") or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Gateway B: Direct Instagram Embed Scraper
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(f"https://www.instagram.com/reel/{shortcode}/embed/captioned/", headers=headers, timeout=8)
        if res.status_code == 200:
            html_text = res.text
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', html_text) or re.findall(r'"video_url":"([^"]+)"', html_text)
            if v_matches:
                v_clean = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": v_clean,
                    "thumbnail": f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- ૨. YOUTUBE ENGINE ---
def extract_youtube_video(raw_url: str):
    vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', raw_url)
    if not vid_match:
        return None
    video_id = vid_match.group(1)

    invidious_endpoints = [
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de",
        "https://invidious.protokolla.fi"
    ]
    for endpoint in invidious_endpoints:
        try:
            res = requests.get(f"{endpoint}/api/v1/videos/{video_id}", timeout=6)
            if res.status_code == 200:
                data = res.json()
                formats = data.get("formatStreams", [])
                if formats:
                    return {
                        "title": data.get("title", "YouTube Video"),
                        "download_url": formats[-1].get("url"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "platform": "YouTube"
                    }
        except Exception:
            continue
    return None

# --- ૩. TIKTOK & OTHER SOCIAL MEDIA ---
def extract_universal_video(raw_url: str):
    nodes = ["https://api.cobalt.tools", "https://cobalt-api.kwiatekm.tokyo", "https://api.server.ovh/cobalt"]
    for node in nodes:
        try:
            r = requests.post(node, json={"url": raw_url.strip().rstrip(','), "videoQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=7)
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

@app.post("/download")
def download_endpoint(req: VideoRequest):
    raw_url = req.url.strip()

    # 1. Instagram
    if "instagram.com" in raw_url:
        res = extract_instagram_reel(raw_url)
        if res:
            return {"status": "success", "data": res}

    # 2. YouTube / Shorts
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        res = extract_youtube_video(raw_url)
        if res:
            return {"status": "success", "data": res}

    # 3. TikTok / Facebook / Other
    res = extract_universal_video(raw_url)
    if res:
        return {"status": "success", "data": res}

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure the link is public and valid.")
