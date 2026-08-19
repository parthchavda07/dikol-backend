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
    # URL માંથી વધારાના tracking parameters હટાવવા
    return url.split('?')[0].strip()

# ૧. Instagram Reels માટે 429 Rate-Limit Bypass એન્જિન
def fetch_instagram_video(url: str):
    clean = clean_url(url)
    
    # Instagram GraphQL / Public Embed Scraper
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # Method A: Instagram Direct JSON API
    try:
        json_url = f"{clean}/?__a=1&__d=dis"
        res = requests.get(json_url, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            if items:
                item = items[0]
                video_versions = item.get("video_versions", [])
                if video_versions:
                    video_url = video_versions[0].get("url")
                    thumb = item.get("image_versions2", {}).get("candidates", [{}])[0].get("url", "")
                    return {
                        "status": "success",
                        "success": True,
                        "data": {
                            "title": "Instagram Reel",
                            "download_url": video_url,
                            "thumbnail": thumb or "https://via.placeholder.com/300x200?text=Instagram+Reel",
                            "duration": "HD",
                            "platform": "Instagram"
                        }
                    }
    except Exception:
        pass

    # Method B: Fast Instagram Scraper API Gateway
    try:
        api_gateway = f"https://api.vkrdownloader.com/server?vkr={clean}"
        res = requests.get(api_gateway, timeout=7)
        if res.status_code == 200:
            data = res.json().get("data", {})
            video_url = data.get("download_url") or data.get("url")
            if video_url:
                return {
                    "status": "success",
                    "success": True,
                    "data": {
                        "title": data.get("title", "Instagram Reel"),
                        "download_url": video_url,
                        "thumbnail": data.get("thumbnail", "https://via.placeholder.com/300x200?text=Instagram+Reel"),
                        "duration": "HD",
                        "platform": "Instagram"
                    }
                }
    except Exception:
        pass

    return None

# ૨. YouTube & Shorts Resolver
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
            r = requests.get(f"{cdn}/api/v1/videos/{video_id}", timeout=5)
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
    url = req.url.strip()

    # ૧. જો Instagram ની લિંક હોય
    if "instagram.com" in url:
        insta_res = fetch_instagram_video(url)
        if insta_res:
            return insta_res

    # ૨. જો YouTube ની લિંક હોય
    if "youtube.com" in url or "youtu.be" in url:
        yt_res = fetch_youtube_direct_stream(url)
        if yt_res:
            return yt_res

    # ૩. TikTok, Facebook અને અન્ય સાઇટ્સ માટે yt-dlp
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url(url), download=False)
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
