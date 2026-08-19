"""
Multi-platform video downloader backend.
Supports Instagram Reels, YouTube Shorts/Videos, TikTok (no watermark), Facebook Videos.

Extraction is done with yt-dlp, which is actively maintained against platform
changes (far more robust than hand-rolled scrapers). A /stream endpoint
re-resolves and proxies the binary so the browser gets a real .mp4 with a
Content-Disposition header, never an HTML error page or third-party redirect.
"""

import os
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# --------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------

app = FastAPI(title="Video Downloader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Tracking / junk query params to strip from incoming URLs.
TRACKING_PARAMS = {
    "igsh", "igshid", "si", "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "feature", "fbclid", "share_app_id",
    "spm", "s", "source",
}

# Optional cookie files (Netscape format) for platforms that gate content
# behind login or aggressively bot-detect anonymous requests. Set these as
# environment variables on your host (e.g. Render's "Secret Files").
# Without cookies, public/unauthenticated posts still generally work, but
# some Instagram/YouTube requests will fail or get rate-limited harder.
COOKIE_FILES = {
    "instagram": os.environ.get("IG_COOKIES_FILE"),
    "youtube": os.environ.get("YT_COOKIES_FILE"),
    "facebook": os.environ.get("FB_COOKIES_FILE"),
    "tiktok": os.environ.get("TT_COOKIES_FILE"),
}


# --------------------------------------------------------------------------
# URL sanitation & platform detection
# --------------------------------------------------------------------------

def sanitize_url(raw_url: str) -> str:
    """Strip whitespace, stray commas/quotes, and tracking query params."""
    if not raw_url or not raw_url.strip():
        raise HTTPException(400, "URL is required")

    url = raw_url.strip()
    # Remove trailing commas / stray punctuation users often paste along with a link
    url = url.strip(" ,;\t\n\"'")

    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(400, "Invalid URL: must start with http:// or https://")

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    clean_query = {k: v for k, v in query.items() if k.lower() not in TRACKING_PARAMS}
    new_query = urlencode(clean_query, doseq=True)

    cleaned = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", parsed.params, new_query, "")
    )
    return cleaned


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "instagram.com" in host:
        return "instagram"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    if "facebook.com" in host or "fb.watch" in host:
        return "facebook"
    raise HTTPException(400, "Unsupported platform. Supported: Instagram, YouTube, TikTok, Facebook.")


# --------------------------------------------------------------------------
# yt-dlp helpers
# --------------------------------------------------------------------------

def build_ydl_opts(platform: str) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
        "http_headers": {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        "extractor_retries": 3,
        "retries": 3,
        "socket_timeout": 20,
        "geo_bypass": True,
        "nocheckcertificate": True,
    }

    cookie_file = COOKIE_FILES.get(platform)
    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    if platform == "youtube":
        # android client tends to dodge the "Sign in to confirm you're not a
        # bot" wall better than the default web client
        opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
    if platform == "tiktok":
        opts["extractor_args"] = {"tiktok": {"webpage_download": ["true"]}}

    return opts


def extract_info(clean_url: str, platform: str) -> dict:
    opts = build_ydl_opts(platform)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "429" in msg or "Too Many Requests" in msg:
            raise HTTPException(
                429,
                "The source platform is rate-limiting this server right now. "
                "Please retry in a minute.",
            )
        if "private" in msg.lower() or "login" in msg.lower() or "rate-limit" in msg.lower():
            raise HTTPException(
                403,
                "This content requires login/cookies to access, or is private/age-restricted.",
            )
        raise HTTPException(400, f"Could not extract this video: {msg[:200]}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Unexpected extraction error: {str(e)[:200]}")

    if not info:
        raise HTTPException(404, "Video not found")
    return info


def pick_best_format(info: dict):
    """Return (direct_url, ext) for the best progressive (video+audio) mp4-ish stream."""
    direct_url = info.get("url")
    ext = info.get("ext", "mp4")

    formats = info.get("formats") or []
    if formats:
        # Prefer formats that already have both audio and video muxed
        # (progressive) since we are not running ffmpeg to merge streams.
        progressive = [
            f for f in formats
            if f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")
        ]
        candidates = progressive or [f for f in formats if f.get("vcodec") not in (None, "none")]
        if candidates:
            def score(f):
                mp4_bonus = 1 if f.get("ext") == "mp4" else 0
                return (mp4_bonus, f.get("height") or 0, f.get("tbr") or 0)

            best = max(candidates, key=score)
            direct_url = best.get("url") or direct_url
            ext = best.get("ext", ext)

    return direct_url, ext


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class InfoRequest(BaseModel):
    url: str


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/info")
def get_info(payload: InfoRequest):
    """Resolve metadata + thumbnail for a pasted link. Does NOT download anything."""
    clean_url = sanitize_url(payload.url)
    platform = detect_platform(clean_url)
    info = extract_info(clean_url, platform)

    direct_url, ext = pick_best_format(info)
    if not direct_url:
        raise HTTPException(404, "No downloadable stream found for this video")

    title = info.get("title") or "video"
    safe_title = re.sub(r"[^a-zA-Z0-9_\- ]", "", title)[:80].strip() or "video"

    return {
        "platform": platform,
        "title": title,
        "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "filename": f"{safe_title}.{ext}",
        # The frontend calls /stream with the ORIGINAL page url (not the
        # short-lived direct_url) because signed CDN URLs expire quickly.
        "stream_url": f"/stream?url={httpx.QueryParams({'url': payload.url})['url']}&filename={httpx.QueryParams({'filename': safe_title})['filename']}",
    }


@app.get("/stream")
def stream_video(url: str = Query(..., description="Original page URL"),
                  filename: Optional[str] = Query(None)):
    """
    Re-resolves the link and proxies the raw video bytes back to the browser
    with Content-Disposition: attachment, so clicking Download saves a real
    playable .mp4 instead of redirecting to the source site.
    """
    clean_url = sanitize_url(url)
    platform = detect_platform(clean_url)
    info = extract_info(clean_url, platform)

    direct_url, ext = pick_best_format(info)
    if not direct_url:
        raise HTTPException(404, "No stream URL found for this video")

    safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", filename or info.get("title") or "video")[:80].strip() or "video"
    if not safe_name.lower().endswith(f".{ext}"):
        safe_name = f"{safe_name}.{ext}"

    req_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}

    client = httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        upstream = client.send(
            client.build_request("GET", direct_url, headers=req_headers), stream=True
        )
    except httpx.HTTPError as e:
        client.close()
        raise HTTPException(502, f"Could not reach the video source: {str(e)[:200]}")

    if upstream.status_code >= 400:
        upstream.close()
        client.close()
        raise HTTPException(upstream.status_code, "Source rejected the download request")

    content_type = upstream.headers.get("content-type", "video/mp4")
    if not content_type.startswith("video"):
        content_type = "video/mp4"

    def iter_bytes():
        try:
            for chunk in upstream.iter_bytes(chunk_size=256 * 1024):
                yield chunk
        finally:
            upstream.close()
            client.close()

    return StreamingResponse(
        iter_bytes(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
