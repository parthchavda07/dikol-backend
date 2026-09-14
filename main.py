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
INSTA_HOST = "instagram-looter2.p.rapidapi.com"
YT_HOST = "youtube-video-fast-downloader-24-7.p.rapidapi.com"

# --- ૧. YOUTUBE FAST DOWNLOADER (RAPIDAPI + SMART FALLBACK) ---
def extract_youtube(raw_url: str):
    pattern = r'(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/))([\w-]{11})'
    match = re.search(pattern, raw_url)
    if not match:
        return None

    video_id = match.group(1)
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": YT_HOST
    }

    video_url = None
    audio_url = None
    title = f"YouTube_Video_{video_id}"

    try:
        # MP4 Video Link
        v_res = requests.get(
            f"https://{YT_HOST}/download_video/{video_id}",
            headers=headers,
            timeout=12
        ).json()
        if isinstance(v_res, dict):
            video_url = v_res.get("url") or v_res.get("download_url") or v_res.get("link")
            if v_res.get("title"):
                title = v_res.get("title")

        # MP3 Audio Link
        a_res = requests.get(
            f"https://{YT_HOST}/download_audio/{video_id}",
            headers=headers,
            timeout=12
        ).json()
        if isinstance(a_res, dict):
            audio_url = a_res.get("url") or a_res.get("download_url") or a_res.get("link")
    except Exception:
        pass

    # Reliable fallback if API limits or fails
    if not video_url:
        video_url = f"https://loader.to/api/button/?url=https://www.youtube.com/watch?v={video_id}&f=1080"
    if not audio_url:
        audio_url = f"https://loader.to/api/button/?url=https://www.youtube.com/watch?v={video_id}&f=mp3"

    return {
        "title": title,
        "download_url": video_url,
        "audio_url": audio_url,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "platform": "YouTube"
    }

# --- ૨. UNIVERSAL FALLBACK (YT-DLP FOR TIKTOK/FACEBOOK) ---
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
            formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('vcodec') != 'none']
            video_url = formats[-1].get('url') if formats else info['formats'][-1].get('url')

        return {
            "title": info.get('title') or "video",
            "download_url": video_url,
            "thumbnail": info.get('thumbnail') or "https://images.placeholders.dev/?width=640&height=360&text=Video+Ready",
            "platform": info.get('extractor_key') or "Social Media"
        }

# --- ૩. MAIN DOWNLOAD ROUTE ---
@app.post("/download")
def fetch_download(req: VideoRequest):
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Invalid URL provided.")

    is_instagram = "instagram.com" in raw_url or "instagr.am" in raw_url
    is_youtube = "youtube.com" in raw_url or "youtu.be" in raw_url
    is_tiktok = "tiktok.com" in raw_url
    is_facebook = "facebook.com" in raw_url or "fb.watch" in raw_url

    # A. YOUTUBE HANDLER
    if is_youtube:
        yt_data = extract_youtube(raw_url)
        if yt_data:
            return {"status": "success", "data": yt_data}

    # B. INSTAGRAM HANDLER (WITH REAL THUMBNAIL EXTRACTION)
    if is_instagram:
        clean_url = raw_url.split("?")[0]
        shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean_url)
        shortcode = shortcode_match.group(1) if shortcode_match else ""

        headers = {
            "x-rapidapi-host": INSTA_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY
        }

        api_endpoints = []
        if shortcode:
            api_endpoints.append({
                "url": f"https://{INSTA_HOST}/post",
                "params": {"url": f"https://www.instagram.com/reel/{shortcode}/"}
            })
        api_endpoints.append({
            "url": f"https://{INSTA_HOST}/search",
            "params": {"query": clean_url}
        })

        for ep in api_endpoints:
            try:
                res = requests.get(ep["url"], headers=headers, params=ep["params"], timeout=12)
                if res.status_code == 200:
                    data = res.json()

                    # Find Real MP4
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
                            for _, v in obj.items():
                                found = find_mp4_video(v)
                                if found: return found
                        elif isinstance(obj, list):
                            for item in obj:
                                found = find_mp4_video(item)
                                if found: return found
                        return None

                    # Find Real Thumbnail Image
                    def find_real_thumb(obj):
                        if isinstance(obj, dict):
                            for k in ["thumbnail_url", "display_url", "cover", "picture", "image_versions2"]:
                                if k in obj:
                                    v = obj[k]
                                    if isinstance(v, str) and "http" in v: return v
                                    if isinstance(v, dict) and "candidates" in v and len(v["candidates"]) > 0:
                                        return v["candidates"][0].get("url")
                            for _, v in obj.items():
                                t = find_real_thumb(v)
                                if t: return t
                        elif isinstance(obj, list):
                            for item in obj:
                                t = find_real_thumb(item)
                                if t: return t
                        return None

                    video_url = find_mp4_video(data)
                    raw_thumb = find_real_thumb(data)

                    if raw_thumb:
                        safe_thumb = f"https://wsrv.nl/?url={requests.utils.quote(raw_thumb)}"
                    else:
                        safe_thumb = "https://images.placeholders.dev/?width=640&height=360&text=Instagram+Reel"

                    if video_url:
                        return {
                            "status": "success",
                            "data": {
                                "title": f"Instagram_Reel_{shortcode}" if shortcode else "Instagram_Video",
                                "download_url": video_url,
                                "thumbnail": safe_thumb,
                                "platform": "Instagram"
                            }
                        }
            except Exception:
                continue

    # C. TIKTOK / FACEBOOK / OTHER HANDLER
    if is_tiktok or is_facebook:
        try:
            data = extract_via_ytdlp(raw_url)
            if data.get("download_url"):
                return {"status": "success", "data": data}
        except Exception:
            pass

    # D. FINAL UNIVERSAL FALLBACK
    try:
        data = extract_via_ytdlp(raw_url)
        if data.get("download_url"):
            return {"status": "success", "data": data}
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Could not extract video. Please make sure the link is public.")

# --- ૪. STREAMING PROXY ROUTE ---
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
