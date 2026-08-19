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

# YouTube અને અન્ય સોશિયલ મીડિયા માટે Cobalt API એન્જિન
def fetch_via_cobalt(url: str):
    endpoints = [
        "https://api.cobalt.tools",
        "https://cobalt-api.kwiatekm.tokyo",
        "https://api.server.ovh/cobalt",
        "https://cobalt.synced.team"
    ]
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    payload = {
        "url": url,
        "videoQuality": "720",
        "youtubeVideoCodec": "h264"
    }
    
    for endpoint in endpoints:
        try:
            res = requests.post(endpoint, json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                # Cobalt v10 response: url / tunnel
                download_url = data.get("url")
                if download_url:
                    # થંબનેલ નક્કી કરવું
                    thumbnail = "https://via.placeholder.com/640x360?text=Video+Ready"
                    if "youtube.com" in url or "youtu.be" in url:
                        vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
                        if vid_match:
                            thumbnail = f"https://img.youtube.com/vi/{vid_match.group(1)}/hqdefault.jpg"

                    return {
                        "status": "success",
                        "success": True,
                        "data": {
                            "title": data.get("filename") or "Social Media Video",
                            "download_url": download_url,
                            "thumbnail": thumbnail,
                            "duration": "HD",
                            "platform": "Universal Downloader"
                        }
                    }
        except Exception:
            continue
    return None

@app.post("/download")
def extract_video(req: VideoRequest):
    url = clean_url(req.url)
    
    # ૧. પહેલા હાઇ-સ્પીડ API વડે ચેક કરો (YouTube, TikTok, Insta, FB બધું જ હેન્ડલ કરે છે)
    cobalt_res = fetch_via_cobalt(url)
    if cobalt_res:
        return cobalt_res

    # ૨. જો API બિઝી હોય તો yt-dlp ફૉલબેક
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
