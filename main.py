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

def fetch_youtube_streams(url: str):
    video_id = get_youtube_video_id(url)
    if not video_id:
        return None

    # મલ્ટીપલ પબ્લિક Invidious ઇન્સ્ટન્સ જે YouTube Botguard વગર ડાયરેક્ટ વીડિયો સ્ટ્રીમ્સ આપે છે
    instances = [
        "https://invidious.nerdvpn.de",
        "https://inv.tux.pizza",
        "https://invidious.protokolla.fi",
        "https://yt.drgnz.club"
    ]
    
    for instance in instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            res = requests.get(api_url, timeout=6)
            if res.status_code == 200:
                data = res.json()
                title = data.get("title", "YouTube Video")
                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                
                # ઓડિયો અને વિડિયો બંને સાથે હોય તેવી બેસ્ટ ફોર્મેટ લિંક
                formats = data.get("formatStreams", [])
                if formats:
                    # સૌથી હાઈ-ક્વોલિટી પસંદ કરો
                    download_url = formats[-1].get("url")
                    return {
                        "status": "success",
                        "success": True,
                        "data": {
                            "title": title,
                            "download_url": download_url,
                            "thumbnail": thumbnail,
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
    
    # જો YouTube અથવા Shorts હોય
    if "youtube.com" in url or "youtu.be" in url:
        yt_data = fetch_youtube_streams(url)
        if yt_data:
            return yt_data

    # અન્ય તમામ પ્લેટફોર્મ (Instagram, TikTok, FB) માટે yt-dlp
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
