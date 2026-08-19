import re
import html
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
    return url.split('?')[0].strip()

# ૧. Instagram Reels/Video Scraper (Embed Method - 100% Working)
def fetch_instagram_embed(url: str):
    shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', url)
    if not shortcode_match:
        return None
    shortcode = shortcode_match.group(1)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    try:
        # Instagram Embed Page Scrape
        embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
        r = requests.get(embed_url, headers=headers, timeout=8)
        if r.status_code == 200:
            html_text = r.text
            # Video URL શોધવા માટે
            video_matches = re.findall(r'video_url\\":\\"([^"\\]+)', html_text)
            if not video_matches:
                video_matches = re.findall(r'"video_url":"([^"]+)"', html_text)
                
            if video_matches:
                clean_video_url = video_matches[0].replace('\\u0026', '&').replace('\\/', '/')
                clean_video_url = html.unescape(clean_video_url)
                
                # Thumbnail શોધવા માટે
                thumb_match = re.findall(r'display_url\\":\\"([^"\\]+)', html_text)
                thumb = ""
                if thumb_match:
                    thumb = thumb_match[0].replace('\\u0026', '&').replace('\\/', '/')
                    thumb = html.unescape(thumb)

                return {
                    "status": "success",
                    "success": True,
                    "data": {
                        "title": f"Instagram Reel ({shortcode})",
                        "download_url": clean_video_url,
                        "thumbnail": thumb or "https://via.placeholder.com/300x200?text=Instagram+Reel",
                        "duration": "HD",
                        "platform": "Instagram"
                    }
                }
    except Exception:
        pass
    return None

# ૨. YouTube & Shorts Resolver
def fetch_youtube_video(url: str):
    vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
    if not vid_match:
        return None
    video_id = vid_match.group(1)

    instances = [
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de",
        "https://invidious.protokolla.fi"
    ]
    for cdn in instances:
        try:
            res = requests.get(f"{cdn}/api/v1/videos/{video_id}", timeout=6)
            if res.status_code == 200:
                data = res.json()
                formats = data.get("formatStreams", [])
                if formats:
                    return {
                        "status": "success",
                        "success": True,
                        "data": {
                            "title": data.get("title", "YouTube Video"),
                            "download_url": formats[-1].get("url"),
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

    # ૧. જો Instagram હોય
    if "instagram.com" in url:
        insta = fetch_instagram_embed(url)
        if insta:
            return insta

    # ૨. જો YouTube હોય
    if "youtube.com" in url or "youtu.be" in url:
        yt = fetch_youtube_video(url)
        if yt:
            return yt

    # ૩. TikTok, Facebook અને અન્ય
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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

            if video_url:
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
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Could not extract video. Please ensure link is public.")
