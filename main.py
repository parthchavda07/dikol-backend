import re
import html
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

def clean_url(raw: str) -> str:
    u = raw.strip().replace(',', '').strip()
    return u.split('?')[0].split('&')[0]

# --- 1. INSTAGRAM ENGINE ---
def fetch_instagram(url: str):
    clean = clean_url(url)
    m = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', clean)
    if not m:
        return None
    shortcode = m.group(1)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
        r = requests.get(embed_url, headers=headers, timeout=8)
        if r.status_code == 200:
            v_matches = re.findall(r'video_url\\":\\"([^"\\]+)', r.text) or re.findall(r'"video_url":"([^"]+)"', r.text)
            if v_matches:
                v_clean = html.unescape(v_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                t_matches = re.findall(r'display_url\\":\\"([^"\\]+)', r.text)
                t_clean = html.unescape(t_matches[0].replace('\\u0026', '&').replace('\\/', '/')) if t_matches else ""
                return {
                    "title": f"Instagram Reel ({shortcode})",
                    "download_url": v_clean,
                    "thumbnail": t_clean or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    try:
        api_res = requests.get(f"https://api.vkrdownloader.com/server?vkr=https://www.instagram.com/reel/{shortcode}/", timeout=8)
        if api_res.status_code == 200:
            d = api_res.json().get("data", {})
            v_url = d.get("download_url") or d.get("url")
            if v_url:
                return {
                    "title": d.get("title") or f"Instagram Reel ({shortcode})",
                    "download_url": v_url,
                    "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                    "platform": "Instagram"
                }
    except Exception:
        pass

    return None

# --- 2. FACEBOOK ENGINE ---
def fetch_facebook(url: str):
    clean = url.strip().replace(',', '').strip()
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr={clean}", timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                return {
                    "title": d.get("title") or "Facebook Video",
                    "download_url": v,
                    "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Facebook+Video",
                    "platform": "Facebook"
                }
    except Exception:
        pass

    # Method B: Direct Cobalt FB Engine
    try:
        c_res = requests.post(
            "https://api.cobalt.tools", 
            json={"url": clean, "videoQuality": "720"}, 
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=7
        )
        if c_res.status_code == 200:
            d = c_res.json()
            if d.get("url"):
                return {
                    "title": d.get("filename") or "Facebook Video",
                    "download_url": d.get("url"),
                    "thumbnail": "https://via.placeholder.com/640x360?text=Facebook+Video",
                    "platform": "Facebook"
                }
    except Exception:
        pass

    return None

# --- 3. YOUTUBE / SHORTS ENGINE ---
def fetch_youtube(url: str):
    clean = clean_url(url)
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', clean)
    if not m:
        return None
    video_id = m.group(1)

    hosts = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de", "https://invidious.protokolla.fi"]
    for h in hosts:
        try:
            r = requests.get(f"{h}/api/v1/videos/{video_id}", timeout=6)
            if r.status_code == 200:
                streams = r.json().get("formatStreams", [])
                if streams:
                    return {
                        "title": r.json().get("title", "YouTube Video"),
                        "download_url": streams[-1].get("url"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "platform": "YouTube"
                    }
        except Exception:
            continue
    return None

# --- MAIN DOWNLOAD DETAILS ENDPOINT ---
@app.post("/download")
def download_details(req: VideoRequest):
    raw_url = req.url.strip()

    # Facebook
    if "facebook.com" in raw_url or "fb.watch" in raw_url:
        fb_data = fetch_facebook(raw_url)
        if fb_data:
            return {"status": "success", "data": fb_data}

    # Instagram
    if "instagram.com" in raw_url:
        insta_data = fetch_instagram(raw_url)
        if insta_data:
            return {"status": "success", "data": insta_data}

    # YouTube
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        yt_data = fetch_youtube(raw_url)
        if yt_data:
            return {"status": "success", "data": yt_data}

    # TikTok & Others
    try:
        r = requests.get(f"https://api.vkrdownloader.com/server?vkr={raw_url}", timeout=8)
        if r.status_code == 200:
            d = r.json().get("data", {})
            v = d.get("download_url") or d.get("url")
            if v:
                return {
                    "status": "success",
                    "data": {
                        "title": d.get("title") or "Social Media Video",
                        "download_url": v,
                        "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Video+Ready",
                        "platform": "Social Media"
                    }
                }
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Could not extract video. Please make sure the post is public.")

# --- PROXY STREAM (ક્યારેય કરપ્ટ ફાઈલ ન આવે તે માટે સાચો MP4 બાઈનરી ડાઉનલોડ પાથ) ---
@app.get("/stream")
def stream_file(video_url: str, title: str = "video"):
    try:
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:30] or "video"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        req = requests.get(video_url, headers=headers, stream=True, timeout=15)
        
        return StreamingResponse(
            req.iter_content(chunk_size=1024 * 1024),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_title}.mp4"'
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Stream failed.")
