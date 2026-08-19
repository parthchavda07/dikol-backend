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

# YouTube માટે Cobalt API (Render Botguard બાયપાસ કરવા માટે)
def fetch_youtube_cobalt(url: str):
    try:
        api_endpoints = [
            "https://api.cobalt.tools/api/json",
            "https://cobalt-backend.canine.tools/api/json"
        ]
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "vQuality": "720",
            "isAudioOnly": False
        }
        for endpoint in api_endpoints:
            try:
                res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("url"):
                        return {
                            "status": "success",
                            "success": True,
                            "data": {
                                "title": "YouTube Video",
                                "download_url": data.get("url"),
                                "thumbnail": "https://img.youtube.com/vi/" + (url.split('/')[-1].split('?')[0]) + "/hqdefault.jpg",
                                "duration": "HD",
                                "platform": "YouTube"
                            }
                        }
            except Exception:
                continue
    except Exception:
        pass
    return None

@app.post("/download")
def extract_video(req: VideoRequest):
    url = clean_url(req.url)
    
    # જો YouTube / Shorts હોય તો પહેલા એક્સટર્નલ એન્જિન વાપરો
    if "youtube.com" in url or "youtu.be" in url:
        cobalt_result = fetch_youtube_cobalt(url)
        if cobalt_result:
            return cobalt_result

    # અન્ય પ્લેટફોર્મ (Instagram, TikTok, FB) માટે yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

            title = info.get('title', 'Social Media Video')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration_string', '0:30')
            extractor = info.get('extractor_key', 'Social Media')

            return {
                "status": "success",
                "success": True,
                "data": {
                    "title": title,
                    "download_url": video_url,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "platform": extractor
                }
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not extract video: {str(e)}")
