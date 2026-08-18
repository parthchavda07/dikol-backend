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

@app.post("/download")
def extract_video(req: VideoRequest):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            video_url = info.get('url')
            title = info.get('title', 'Downloaded Video')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration_string', '0:30')

            return {
                "success": True,
                "title": title,
                "download_url": video_url,
                "thumbnail": thumbnail,
                "duration": duration
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))