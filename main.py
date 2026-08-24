import os
import re
import requests
import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Dikol Multi-Platform Downloader")

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

def extract_via_ytdlp(url: str):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
        'socket_timeout': 15,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_url = info.get('url')
        if not video_url and 'formats' in info:
            # Get highest quality mp4 format with video+audio
            formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('vcodec') != 'none']
            if formats:
                video_url = formats[-1].get('url')
            else:
                video_url = info['formats'][-1].get('url')

        return {
            "title": info.get('title') or "video",
            "download_url": video_url,
            "thumbnail": info.get('thumbnail') or "https://via.placeholder.com/640x360?text=Video+Ready",
            "platform": info.get('extractor_key') or "Social Media"
        }

@app.post("/download")
def fetch_download(req: VideoRequest):
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Invalid URL provided.")

    is_instagram = "instagram.com" in raw_url or "instagr.am" in raw_url
    is_tiktok = "tiktok.com" in raw_url
    is_youtube = "youtube.com" in raw_url or "youtu.be" in raw_url
    is_facebook = "facebook.com" in raw_url or "fb.watch" in raw_url

    # Method 1: If TikTok, YouTube, Facebook, or Twitter -> Use yt-dlp Directly
    if is_tiktok or is_youtube or is_facebook:
        try:
            data = extract_via_ytdlp(raw_url)
            if data.get("download_url"):
                return {"status": "success", "data": data}
        except Exception as e:
            pass

    # Method 2: If Instagram -> Try RapidAPI First, then Fallback to yt-dlp
    if is_instagram:
        clean_url = raw_url.split("?")[0]
        shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean_url)
        shortcode = shortcode_match.group(1) if shortcode_match else ""

        headers = {
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY
        }

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

        for ep in api_endpoints:
            try:
                res = requests.get(ep["url"], headers=headers, params=ep["params"], timeout=12)
                if res.status_code == 200:
                    data = res.json()

                    def find_mp4_video(obj):
                        if isinstance(obj, dict):
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
                        return {
                            "status": "success",
                            "data": {
                                "title": f"Instagram_Reel_{shortcode}" if shortcode else "Instagram_Video",
                                "download_url": video_url,
                                "thumbnail": thumbnail_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                                "platform": "Instagram"
                            }
                        }
            except Exception:
                continue

    # Final Universal Fallback for any link
    try:
        data = extract_via_ytdlp(raw_url)
        if data.get("download_url"):
            return {"status": "success", "data": data}
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Could not extract video. Please make sure the link is public.")

# Streamer (Forces Direct Browser File Download)
@app.get("/stream")
def stream_media(video_url: str = Query(...), title: str = Query("video")):
    try:
        clean_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:40] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(video_url, headers=headers, stream=True, timeout=35)
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
        raise HTTPException(status_code=400, detail="Stream failed or link expired.")
