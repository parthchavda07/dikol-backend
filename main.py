import re
import html
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

# Universal Downloader Engine
@app.post("/download")
def download_video(req: VideoRequest):
    raw_url = req.url.strip()
    url = clean_url(raw_url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    # ==========================================
    # 1. INSTAGRAM REELS ENGINE
    # ==========================================
    if "instagram.com" in raw_url:
        shortcode_match = re.search(r'(?:reel|p|reels)\/([A-Za-z0-9_-]+)', raw_url)
        if shortcode_match:
            shortcode = shortcode_match.group(1)
            
            # Method A: Instagram Embed Extraction
            try:
                embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
                r = requests.get(embed_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    video_matches = re.findall(r'video_url\\":\\"([^"\\]+)', r.text) or re.findall(r'"video_url":"([^"]+)"', r.text)
                    if video_matches:
                        v_url = html.unescape(video_matches[0].replace('\\u0026', '&').replace('\\/', '/'))
                        t_matches = re.findall(r'display_url\\":\\"([^"\\]+)', r.text)
                        t_url = html.unescape(t_matches[0].replace('\\u0026', '&').replace('\\/', '/')) if t_matches else ""
                        return {
                            "status": "success",
                            "data": {
                                "title": f"Instagram Reel ({shortcode})",
                                "download_url": v_url,
                                "thumbnail": t_url or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                                "platform": "Instagram"
                            }
                        }
            except Exception:
                pass

            # Method B: Fast Social API Gateway
            try:
                api_res = requests.get(f"https://api.vkrdownloader.com/server?vkr={url}", timeout=8)
                if api_res.status_code == 200:
                    d = api_res.json().get("data", {})
                    v_url = d.get("download_url") or d.get("url")
                    if v_url:
                        return {
                            "status": "success",
                            "data": {
                                "title": d.get("title") or "Instagram Reel",
                                "download_url": v_url,
                                "thumbnail": d.get("thumbnail") or "https://via.placeholder.com/640x360?text=Instagram+Reel",
                                "platform": "Instagram"
                            }
                        }
            except Exception:
                pass

    # ==========================================
    # 2. YOUTUBE / SHORTS ENGINE
    # ==========================================
    if "youtube.com" in raw_url or "youtu.be" in raw_url:
        vid_match = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', raw_url)
        if vid_match:
            video_id = vid_match.group(1)
            # Fast CDN Resolvers
            mirrors = ["https://inv.tux.pizza", "https://invidious.nerdvpn.de", "https://invidious.protokolla.fi"]
            for m in mirrors:
                try:
                    y_res = requests.get(f"{m}/api/v1/videos/{video_id}", timeout=6)
                    if y_res.status_code == 200:
                        y_data = y_res.json()
                        streams = y_data.get("formatStreams", [])
                        if streams:
                            return {
                                "status": "success",
                                "data": {
                                    "title": y_data.get("title", "YouTube Video"),
                                    "download_url": streams[-1].get("url"),
                                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                    "platform": "YouTube"
                                }
                            }
                except Exception:
                    continue

    # ==========================================
    # 3. TIKTOK & UNIVERSAL GATEWAY
    # ==========================================
    try:
        cobalt_nodes = ["https://api.cobalt.tools", "https://cobalt-api.kwiatekm.tokyo", "https://api.server.ovh/cobalt"]
        for node in cobalt_nodes:
            try:
                c_res = requests.post(node, json={"url": raw_url, "videoQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=7)
                if c_res.status_code == 200:
                    c_data = c_res.json()
                    if c_data.get("url"):
                        return {
                            "status": "success",
                            "data": {
                                "title": c_data.get("filename") or "Social Media Video",
                                "download_url": c_data.get("url"),
                                "thumbnail": "https://via.placeholder.com/640x360?text=Video+Ready",
                                "platform": "Social Media"
                            }
                        }
            except Exception:
                continue
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Unable to extract video stream. Please ensure the link is public.")
