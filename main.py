import re
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

@app.post("/download")
def extract_video(req: VideoRequest):
    url = clean_url(req.url)
    
    ydl_opts = {
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        # YouTube નું Botguard બાયપાસ કરવા માટે TV / Android Client
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'android', 'web_creator', 'ios']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (SmartHub; SMART-TV; U; Linux/SmartTV; Maple2012) AppleWebKit/535.20+ (KHTML, like Gecko) SmartTV Safari/535.20+',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # વિડિયો URL શોધવી
            video_url = info.get('url')
            if not video_url and 'formats' in info:
                # ઓડિયો અને વિડિયો બંને હોય તેવું શ્રેષ્ઠ ફોર્મેટ પસંદ કરવું
                formats = [
                    f for f in info['formats'] 
                    if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none'
                ]
                if not formats:
                    formats = [f for f in info['formats'] if f.get('url') and f.get('vcodec') != 'none']
                
                if formats:
                    video_url = formats[-1].get('url')

            if not video_url:
                raise Exception("Direct download link not found")

            title = info.get('title', 'YouTube Video')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration_string', '0:00')
            extractor = info.get('extractor_key', 'YouTube')

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
