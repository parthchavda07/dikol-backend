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

                # Search strictly for MP4 / Video URLs (Reject .jpg / images)
                def find_mp4_video(obj):
                    if isinstance(obj, dict):
                        # Priority 1: Check explicit video fields
                        for key in ["video_url", "video_versions", "video", "download_url"]:
                            if key in obj:
                                val = obj[key]
                                if isinstance(val, str) and (".mp4" in val or "mime_type=video" in val or "mp4" in val.lower()):
                                    if not val.endswith(".jpg") and not val.endswith(".png"):
                                        return val
                                elif isinstance(val, list) and len(val) > 0:
                                    first_item = val[0]
                                    if isinstance(first_item, dict) and "url" in first_item:
                                        return first_item["url"]

                        for k, v in obj.items():
                            found = find_mp4_video(v)
                            if found:
                                return found

                    elif isinstance(obj, list):
                        for item in obj:
                            found = find_mp4_video(item)
                            if found:
                                return found
                    return None

                video_url = find_mp4_video(data)
                if video_url:
                    thumbnail_url = f"https://images.weserv.nl/?url=https://www.instagram.com/p/{shortcode}/media/?size=l" if shortcode else ""
                    break
        except Exception:
            continue

    if not video_url:
        raise HTTPException(status_code=400, detail="Could not find MP4 video in this link. Please ensure it is a video reel.")

    return {
        "status": "success",
        "data": {
            "title": f"Instagram_Reel_{shortcode}" if shortcode else "Instagram_Video",
            "download_url": video_url,
            "thumbnail": thumbnail_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
            "platform": "Instagram"
        }
    }

# Force Download Streamer (Forces Browser to download .mp4 file directly)
@app.get("/stream")
def stream_media(video_url: str = Query(...), title: str = Query("video")):
    try:
        clean_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:35] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=30)
        res.raise_for_status()

        return StreamingResponse(
            res.iter_content(chunk_size=1024 * 512),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_title}.mp4"',
                "Content-Type": "video/mp4"
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Stream failed.")
