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

def clean_social_url(url: str) -> str:
    # છેડેથી કૉમા, સ્લેશ કે સ્પેસ સાફ કરવા
    url = url.strip().rstrip(',').rstrip('/')
    url = url.split('?')[0].split('&')[0]
    return url

# --- 1. INSTAGRAM ENGINE ---
def extract_instagram(url: str):
    clean = clean_social_url(url)
    match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean)
    if not match:
        return None
    shortcode = match.group(1)

    # Scraper Gateway A (Fast API)
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr=https://www.instagram.com/reel/{shortcode}/", timeout=8)
        if r.status_code == 200:
            res_data = r.json().get("data", {})
            v_url = res_data.get("download_url") or res_data.get("url")
            if v_url:
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": v_url,
                    "thumbnail": res_data.get("thumbnail") or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Scraper Gateway B (Direct Embed Parser)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        res = requests.get(f"https://www.instagram.com/reel/{shortcode}/embed/captioned/", headers=headers, timeout=8)
        if res.status_code == 200:
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', res.text) or re.findall(r'"video_url":"([^"]+)"', res.text)
            if v_matches:
                video_url = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                t_matches = re.findall(r'display_url\\":\\"([^"\\]+)', res.text)
                t_url = html.unescape(t_matches[0].replace('\\u0026', '&').replace('\\/', '/')) if t_matches else ""
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": video_url,
                    "thumbnail": t_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- 2. YOUTUBE ENGINE ---
def extract_youtube(url: str):
    clean = clean_social_url(url)
    vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', clean)
    if not vid_match:
        return None
    video_id = vid_match.group(1)

    mirrors = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de", "https://invidious.protokolla.fi"]
    for m in mirrors:
        try:
            res = requests.get(f"{m}/api/v1/videos/{video_id}", timeout=6)
            if res.status_code == 200:
                data = res.json()
                streams = data.get("formatStreams", [])
                if streams:
                    return {
                        "title": data.get("title", "YouTube Video"),
                        "download_url": streams[-1].get("url"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "platform": "YouTube"
                    }
        except Exception:
            continue
    return None

# --- 3. UNIVERSAL (TIKTOK / FB) ENGINE ---
def extract_universal(url: str):
    nodes = ["https://api.cobalt.tools", "https://cobalt-api.kwiatekm.tokyo", "https://api.server.ovh/cobalt"]
    for node in nodes:
        try:
            r = requests.post(node, json={"url": url, "videoQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=7)
            if r.status_code == 200:
                data = r.json()
                if data.get("url"):
                    return {
                        "title": data.get("filename") or "Social Media Video",
                        "download_url": data.get("url"),
                        "thumbnail": "https://via.placeholder.com/640x360?text=Video+Ready",
                        "platform": "Social Media"
                    }
        except Exception:
            continue
    return None

@app.post("/download")
def download(req: VideoRequest):
    url = req.url.strip()

    # 1. Instagram
    if "instagram.com" in url:
        res = extract_instagram(url)
        if res:
            return {"status": "success", "data": res}

    # 2. YouTube
    if "youtube.com" in url or "youtu.be" in url:
        res = extract_youtube(url)
        if res:
            return {"status": "success", "data": res}

    # 3. TikTok / Facebook / Other
    res = extract_universal(url)
    if res:
        return {"status": "success", "data": res}

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure the link is valid and public.")
