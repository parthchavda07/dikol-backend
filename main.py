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

def get_clean_id(raw_url: str):
    # Regex: Instagram Shortcode ID Extract (11 digits alphanumeric)
    match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]{10,12})', raw_url)
    if match:
        return match.group(1)
    return None

def fetch_instagram_robust(raw_url: str):
    shortcode = get_clean_id(raw_url)
    if not shortcode:
        # Fallback regex for loose pattern
        m = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', raw_url)
        if m:
            shortcode = m.group(1).rstrip(',').strip()
    
    if not shortcode:
        return None

    # Pipeline A: Multi-Node GraphQL & Direct App API
    app_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 314.0.0.19.108",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": "936619743392459"
    }

    # Endpoint 1: Instagram GraphQL Query
    try:
        gql_url = f"https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables=%7B%22shortcode%22:%22{shortcode}%22%7D"
        r = requests.get(gql_url, headers=app_headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            media = data.get("data", {}).get("shortcode_media", {})
            if media.get("is_video") and media.get("video_url"):
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": media.get("video_url"),
                    "thumbnail": media.get("display_url") or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Endpoint 2: Proxy Gateway Scraper
    try:
        gw_url = f"https://api.vkrdownloader.com/server?vkr=https://www.instagram.com/reel/{shortcode}/"
        r = requests.get(gw_url, timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v_url = d.get("download_url") or d.get("url")
            if v_url:
                return {
                    "title": d.get("title") or f"Instagram Reel ({shortcode})",
                    "download_url": v_url,
                    "thumbnail": d.get("thumbnail") or f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    # Endpoint 3: Fast Embed CDN Parser
    try:
        embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
        r = requests.get(embed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=8)
        if r.status_code == 200:
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', r.text) or re.findall(r'"video_url":"([^"]+)"', r.text)
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

def fetch_youtube_robust(raw_url: str):
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', raw_url)
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

@app.post("/download")
def download_api(req: VideoRequest):
    raw_url = req.url.strip()

    # 1. Instagram
    if "instagram.com" in raw_url:
        data = fetch_instagram_robust(raw_url)
        if data:
            return {"status": "success", "data": data}

    # 2. YouTube
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        data = fetch_youtube_robust(raw_url)
        if data:
            return {"status": "success", "data": data}

    # 3. TikTok & Universal Fallback
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr={raw_url}", timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                return {
                    "status": "success",
                    "data": {
                        "title": d.get("title") or "Social Media Video",
                        "download_url": v,
                        "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Video+Ready",
                        "platform": "Universal"
                    }
                }
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure the link is public and valid.")
