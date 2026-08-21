import os
import re
import requests
from fastapi import FastAPI, HTTPException
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
    clean = raw_url.strip().strip(",").strip()
    return clean.split("?")[0]

@app.post("/download")
def fetch_download(req: VideoRequest):
    clean_url = sanitize_url(req.url)
    if not clean_url:
        raise HTTPException(status_code=400, detail="Invalid URL provided.")

    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean_url)
    shortcode = shortcode_match.group(1) if shortcode_match else ""

    api_endpoints = []
    if shortcode:
        api_endpoints.append({
            "url": "https://instagram-looter2.p.rapidapi.com/post",
            "params": {"url": f"https://www.instagram.com/reel/{shortcode}/"}
        })

    api_endpoints.append({
        "url": "https://instagram-looter2.p.rapidapi.com/search",
        "params": {"query": clean_url}
    })

    video_url = ""
    thumbnail_url = ""

    for ep in api_endpoints:
        try:
            res = requests.get(ep["url"], headers=headers, params=ep["params"], timeout=15)
            if res.status_code == 200:
                data = res.json()

                def extract_video_link(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ["video_url", "download_url", "video", "url"] and isinstance(v, str):
                                if "mp4" in v or "cdninstagram" in v or "fbcdn" in v:
                                    return v
                            found = extract_video_link(v)
                            if found:
                                return found
                    elif isinstance(obj, list):
                        for item in obj:
                            found = extract_video_link(item)
                            if found:
                                return found
                    return None

                video_url = extract_video_link(data)
                if video_url:
                    thumbnail_url = f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l" if shortcode else ""
                    break
        except Exception:
            continue

    if not video_url:
        raise HTTPException(status_code=400, detail="Could not extract video stream.")

    return {
        "status": "success",
        "data": {
            "title": f"Instagram_Reel_{shortcode}" if shortcode else "Instagram_Video",
            "download_url": video_url,
            "thumbnail": thumbnail_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
            "platform": "Instagram"
        }
    }
