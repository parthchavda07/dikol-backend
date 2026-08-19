import re
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

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

def clean_url(url: str) -> str:
    return url.split('?si=')[0].split('&si=')[0].strip()

# YouTube & Shorts માટે ડાયરેક્ટ CDN ફાઈલ મેળવવી
def fetch_youtube_direct_stream(url: str):
    vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
    if not vid_match:
        return None
    
    video_id = vid_match.group(1)
    cdn_instances = [
        "https://invidious.nerdvpn.de",
        "https://inv.tux.pizza",
        "https://invidious.protokolla.fi"
    ]
    
    for cdn in cdn_instances:
        try:
            r = requests.get(f"{cdn}/api/v1/videos/{video_id}", timeout=6)
            if r.status_code == 200:
                data = r.json()
                formats = data.get("formatStreams", [])
                if formats:
                    direct_mp4 = formats[-1].get("url")
                    if direct_mp4:
                        return {
                            "status": "success",
                            "success": True,
                            "data": {
                                "title": data.get("title", "YouTube Video"),
                                "download_url": direct_mp4,
                                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                "duration": "HD",
                                "platform": "YouTube"
                            }
                        }
        except Exception:
            continue
    return None

@app.post("/download")
def extract_video(req: VideoRequest):
    url = clean_url(req.url)
    
    # 1. YouTube & Shorts
    if "youtube.com" in url or "youtu.be" in url:
        yt_data = fetch_youtube_direct_stream(url)
        if yt_data:
            return yt_data

    # 2. Instagram Reels, TikTok, Facebook
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            
            if not video_url and 'formats' in info:
                formats = [f for f in info['formats'] if f.get('url') and f.get('vcodec') != 'none']
                if formats:
                    video_url = formats[-1].get('url')

            if not video_url:
                raise Exception("Direct download link not found")

            return {
                "status": "success",
                "success": True,
                "data": {
                    "title": info.get('title', 'Social Media Video'),
                    "download_url": video_url,
                    "thumbnail": info.get('thumbnail', ''),
                    "duration": info.get('duration_string', '0:30'),
                    "platform": info.get('extractor_key', 'Social Media')
                }
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not extract video: {str(e)}")
