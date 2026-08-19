import re
import html
import json
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

def clean_url_string(raw_url: str) -> str:
    # કૉમા (,), સ્પેસ કે અન્ય બિનજરૂરી ચિહ્નો સાફ કરવા
    u = raw_url.strip().replace(',', '').strip()
    u = u.split('?')[0].split('&')[0]
    return u

# --- ૧. INSTAGRAM SCRAPER ENGINE ---
def get_instagram_stream(url: str):
    clean = clean_url_string(url)
    match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean)
    if not match:
        return None
    shortcode = match.group(1)

    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 314.0.0.19.108',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Method 1: Direct Embed HTML Scrape
    try:
        embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
        r = requests.get(embed_url, headers=headers, timeout=8)
        if r.status_code == 200:
            html_content = r.text
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', html_content) or re.findall(r'"video_url":"([^"]+)"', html_content)
            if v_matches:
                v_clean = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                t_matches = re.findall(r'display_url\\":\\"([^"\\]+)', html_content)
                t_clean = html.unescape(t_matches[0].replace('\\u0026', '&').replace('\\/', '/')) if t_matches else ""
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": v_clean,
                    "thumbnail": t_clean or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Method 2: Rapid SnapInsta CDN Gateway
    try:
        api_url = f"https://api.vkrdownloader.com/server?vkr=https://www.instagram.com/reel/{shortcode}/"
        r = requests.get(api_url, timeout=8)
        if r.status_code == 200:
            res_json = r.json().get("data", {})
            v_url = res_json.get("download_url") or res_json.get("url")
            if v_url:
                return {
                    "title": res_json.get("title") or f"Instagram Reel ({shortcode})",
                    "download_url": v_url,
                    "thumbnail": res_json.get("thumbnail") or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- ૨. YOUTUBE / SHORTS ENGINE ---
def get_youtube_stream(url: str):
    clean = clean_url_string(url)
    vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', clean)
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
def get_universal_stream(url: str):
    nodes = ["https://api.cobalt.tools", "https://cobalt-api.kwiatekm.tokyo", "https://api.server.ovh/cobalt"]
    for node in nodes:
        try:
            r = requests.post(node, json={"url": url, "videoQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=7)
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
def download(req: VideoRequest):
    raw_url = req.url.strip()

    # 1. Instagram
    if "instagram.com" in raw_url:
        result = get_instagram_stream(raw_url)
        if result:
            return {"status": "success", "data": result}

    # 2. YouTube
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        result = get_youtube_stream(raw_url)
        if result:
            return {"status": "success", "data": result}

    # 3. TikTok & Others
    result = get_universal_stream(raw_url)
    if result:
        return {"status": "success", "data": result}

    raise HTTPException(status_code=400, detail="Video extract thayo nathi. Please make sure link is public.")
