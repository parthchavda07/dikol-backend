import os
import re
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Dikol Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

RAPIDAPI_KEY = "58a2ea1d2bmsh1c20c3cbccc4cd8p18074bjsn6c96c833587c"
RAPIDAPI_HOST = "instagram-looter2.p.rapidapi.com"

def sanitize_url(raw_url: str) -> str:
    # Remove whitespace, commas, and trailing slashes
    clean = raw_url.strip().strip(",").strip()
    # Strip tracking parameters (?igsh=, ?utm_source=, etc.)
    clean = clean.split("?")[0]
    return clean

@app.post("/download")
def fetch_download(req: VideoRequest):
    clean_url = sanitize_url(req.url)
    if not clean_url:
        raise HTTPException(status_code=400, detail="Invalid URL provided.")

    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    # Extract shortcode (e.g. DWwXVWVCMgb)
    shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean_url)
    shortcode = shortcode_match.group(1) if shortcode_match else ""

    # Strategy 1: Post / Reel Specific Endpoint
    api_endpoints = []
    if shortcode:
        api_endpoints.append({
            "url": "https://instagram-looter2.p.rapidapi.com/post",
            "params": {"url": f"https://www.instagram.com/reel/{shortcode}/"}
        })
        api_endpoints.append({
            "url": "https://instagram-looter2.p.rapidapi.com/post",
            "params": {"shortcode": shortcode}
        })

    # Strategy 2: Search Query Endpoint (Fallback)
    api_endpoints.append({
        "url": "https://instagram-looter2.p.rapidapi.com/search",
        "params": {"query": clean_url}
    })

    video_url = ""
    thumbnail_url = ""
    title = f"Instagram Reel - {shortcode}" if shortcode else "Instagram Reel"

    for ep in api_endpoints:
        try:
            res = requests.get(ep["url"], headers=headers, params=ep["params"], timeout=15)
            if res.status_code == 200:
                data = res.json()
                
                # Recursive search for video mp4 URL in nested JSON
                def find_video_url(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ["video_url", "download_url", "video", "url"] and isinstance(v, str) and ("mp4" in v or "cdninstagram" in v or "fbcdn" in v):
                                return v
                            res = find_video_url(v)
                            if res:
                                return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_video_url(item)
                            if res:
                                return res
                    return None

                found_url = find_video_url(data)
                if found_url:
                    video_url = found_url
                    thumbnail_url = f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l" if shortcode else ""
                    break
        except Exception:
            continue

    if not video_url:
        raise HTTPException(status_code=400, detail="Could not extract video stream. Please ensure the link is public.")

    return {
        "status": "success",
        "data": {
            "title": title,
            "download_url": video_url,
            "thumbnail": thumbnail_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
            "platform": "Instagram"
        }
    }

@app.get("/stream")
def stream_media(video_url: str = Query(...), title: str = Query("video")):
    try:
        clean_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:35] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=25)
        res.raise_for_status()

        return StreamingResponse(
            res.iter_content(chunk_size=1024 * 512),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_title}.mp4"'
            }
        )
    except requests.RequestException:
        raise HTTPException(status_code=400, detail="Stream failed.")
