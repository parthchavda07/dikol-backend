import re
import requests
from fastapi import FastAPI, HTTPException
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

def clean_url(url: str) -> str:
    return url.split('?')[0].strip()

# Universal Fast Extractor (Instagram, TikTok, YouTube, FB)
def fetch_universal_video(url: str):
    # 1. Direct High-Speed API Engines
    apis = [
        f"https://api.vkrdownloader.com/server?vkr={url}",
        f"https://social-downloader.yt-download.workers.dev/?url={url}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "*/*"
    }

    # API Attempt 1: VKR Gateway
    try:
        r = requests.get(apis[0], headers=headers, timeout=8)
        if r.status_code == 200:
            res_data = r.json().get("data", {})
            video_url = res_data.get("download_url") or res_data.get("url")
            if video_url:
                return {
                    "status": "success",
                    "success": True,
                    "data": {
                        "title": res_data.get("title") or "Downloaded Media",
                        "download_url": video_url,
                        "thumbnail": res_data.get("thumbnail") or "https://via.placeholder.com/640x360?text=Video+Ready",
                        "duration": "HD",
                        "platform": "Social Media"
                    }
                }
    except Exception:
        pass

    # API Attempt 2: Cobalt Public Instances
    cobalt_instances = [
        "https://api.cobalt.tools",
        "https://cobalt-api.kwiatekm.tokyo",
        "https://api.server.ovh/cobalt"
    ]
    cobalt_payload = {
        "url": url,
        "videoQuality": "720",
        "youtubeVideoCodec": "h264"
    }
    
    for instance in cobalt_instances:
        try:
            r = requests.post(
                instance, 
                json=cobalt_payload, 
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=7
            )
            if r.status_code == 200:
                c_data = r.json()
                video_url = c_data.get("url")
                if video_url:
                    thumb = "https://via.placeholder.com/640x360?text=Video+Ready"
                    if "youtube.com" in url or "youtu.be" in url:
                        vid_m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
                        if vid_m:
                            thumb = f"https://img.youtube.com/vi/{vid_m.group(1)}/hqdefault.jpg"

                    return {
                        "status": "success",
                        "success": True,
                        "data": {
                            "title": c_data.get("filename") or "Downloaded Video",
                            "download_url": video_url,
                            "thumbnail": thumb,
                            "duration": "HD",
                            "platform": "Social Media"
                        }
                    }
        except Exception:
            continue

    # API Attempt 3: Invidious Stream (YouTube / Shorts)
    if "youtube.com" in url or "youtu.be" in url:
        vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
        if vid_match:
            video_id = vid_match.group(1)
            invidious_hosts = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de"]
            for host in invidious_hosts:
                try:
                    inv_res = requests.get(f"{host}/api/v1/videos/{video_id}", timeout=6)
                    if inv_res.status_code == 200:
                        formats = inv_res.json().get("formatStreams", [])
                        if formats:
                            return {
                                "status": "success",
                                "success": True,
                                "data": {
                                    "title": inv_res.json().get("title", "YouTube Video"),
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
    url = clean_url(req.url)
    
    result = fetch_universal_video(url)
    if result:
        return result
        
    raise HTTPException(
        status_code=400, 
        detail="Video download link could not be fetched. Please make sure the account/video is public and try again."
    )
