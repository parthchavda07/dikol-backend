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

# Fixed: Wrapped inside quotes
RAPIDAPI_KEY = "442dc61dfamshe5d33deebd3b1f1p11e99ejsn4d6b572d3dd2"
RAPIDAPI_HOST = "instagram-looter2.p.rapidapi.com"

@app.post("/download")
def fetch_download(req: VideoRequest):
    raw_url = req.url.strip().rstrip(",")
    if not raw_url:
        raise HTTPException(status_code=400, detail="Invalid URL")

    api_url = "https://instagram-looter2.p.rapidapi.com/search"
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    params = {"query": raw_url}

    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        # Extract direct video link & thumbnail from API response
        video_url = ""
        thumbnail_url = ""

        # Handles different response structures of Instagram Looter 2
        if isinstance(data, dict):
            video_url = (
                data.get("video_url")
                or data.get("download_url")
                or (data.get("media") and data["media"][0].get("url"))
                or (data.get("links") and data["links"][0].get("url"))
            )
            thumbnail_url = data.get("thumbnail_url") or data.get("picture") or ""
        elif isinstance(data, list) and len(data) > 0:
            video_url = data[0].get("video_url") or data[0].get("url")
            thumbnail_url = data[0].get("thumbnail") or ""

        if not video_url:
            # Fallback if structure is nested
            for k in ["url", "download", "video"]:
                if k in data:
                    video_url = data[k]
                    break

        if not video_url:
            raise HTTPException(status_code=400, detail="Could not extract video stream.")

        return {
            "status": "success",
            "data": {
                "title": data.get("title") or "Instagram Reel",
                "download_url": video_url,
                "thumbnail": thumbnail_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                "platform": "Instagram"
            }
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"RapidAPI request failed: {str(e)}")

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
