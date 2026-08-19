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

def get_youtube_video_id(url: str):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|v\/|shorts\/)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# YouTube વિડિયો ડાઉનલોડ માટે ડાયરેક્ટ API સર્વિસ
def fetch_youtube_direct(url: str):
    video_id = get_youtube_video_id(url)
    if not video_id:
        return None

    # Y2Mate / SaveFrom ક્લાયન્ટ એન્ડપોઈન્ટ
    try:
        api_url = "https://cdn35.savetube.me/info"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        res = requests.post(api_url, json={"url": f"https://www.youtube.com/watch?v={video_id}"}, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json().get("data", {})
            title = data.get("title", "YouTube Video")
            thumbnail = data.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            duration = data.get("durationLabel", "HD")
            
            # વિડિયો ડાઉનલોડ લિંક
            video_formats = data.get("video_formats", [])
            download_url = None
            if video_formats:
                download_url = video_formats[0].get("url")
            
            if not download_url:
                # ફૉલબેક ડાઉનલોડ સર્વિસ
                download_url = f"https://cdn35.savetube.me/download/video/{video_id}/720"

            return {
                "status": "success",
                "success": True,
                "data": {
                    "title": title,
                    "download_url": download_url,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "platform": "YouTube"
                }
            }
    except Exception:
        pass

    # સેકન્ડરી ફૉલબેક
    return {
        "status": "success",
        "success": True,
        "data": {
            "title": "YouTube Video",
            "download_url": f"https://yt1s.com/en/youtube-to-mp4?q=https://www.youtube.com/watch?v={video_id}",
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "duration": "HD",
            "platform": "YouTube"
        }
    }

@app.post("/download")
def extract_video(req: VideoRequest):
    url = clean_url(req.url)
    
    # YouTube & YouTube Shorts માટે
    if "youtube.com" in url or "youtu.be" in url:
        yt_res = fetch_youtube_direct(url)
        if yt_res:
            return yt_res

    # Instagram Reels, TikTok, Facebook માટે yt-dlp
    ydl_opts = {
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
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
