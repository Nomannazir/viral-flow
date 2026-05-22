import logging
import os
from pathlib import Path

import fal_client
import requests

from config import config

logger = logging.getLogger(__name__)

_PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"


def _download(url: str, dest: str, timeout: int = 120) -> str:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return dest


def fetch_pexels_clip(keyword: str, dest: str, min_duration: int = 3) -> str:
    """Download a portrait stock video clip from Pexels matching keyword."""
    if not config.pexels_api_key:
        raise RuntimeError("PEXELS_API_KEY not set — cannot fetch stock clips")

    resp = requests.get(
        _PEXELS_VIDEO_URL,
        headers={"Authorization": config.pexels_api_key},
        params={"query": keyword, "per_page": 10, "size": "medium"},
        timeout=15,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    if not videos:
        raise RuntimeError(f"No Pexels results for: {keyword!r}")

    # Score each file: portrait orientation > HD > long enough
    best_url = None
    best_score = -1
    for video in videos:
        dur = video.get("duration", 0)
        for f in video.get("video_files", []):
            w, h = f.get("width", 0), f.get("height", 0)
            if not w or not h:
                continue
            score = (int(h > w) * 4) + (int(min(w, h) >= 720) * 2) + int(dur >= min_duration)
            if score > best_score:
                best_score = score
                best_url = f["link"]

    if best_url is None:
        best_url = videos[0]["video_files"][0]["link"]

    logger.info(f"Pexels [{keyword[:45]}] → downloading")
    return _download(best_url, dest)


def generate_flux_image(prompt: str, dest: str) -> str:
    """Generate a portrait 9:16 image with FLUX."""
    full_prompt = prompt + ", photorealistic, dramatic lighting, ultra high quality, cinematic"
    result = fal_client.run(
        "fal-ai/flux-pro/v1.1",
        arguments={
            "prompt": full_prompt,
            "image_size": "portrait_16_9",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        },
    )
    img_url = result["images"][0]["url"]
    logger.info(f"FLUX image: {prompt[:55]}")
    return _download(img_url, dest)


def generate_thumbnail(prompt: str, dest: str) -> str:
    """Generate a landscape YouTube thumbnail with FLUX."""
    full_prompt = (
        f"YouTube DIY channel thumbnail, {prompt}, "
        "dramatic before and after, bright colors, eye-catching, "
        "professional photography, high contrast, no text"
    )
    result = fal_client.run(
        "fal-ai/flux-pro/v1.1",
        arguments={
            "prompt": full_prompt,
            "image_size": "landscape_16_9",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        },
    )
    img_url = result["images"][0]["url"]
    return _download(img_url, dest)


def fetch_clips_for_steps(steps: list[dict], clips_dir: str) -> list:
    """Fetch one Pexels clip per step. Returns list of paths (None on failure)."""
    Path(clips_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for i, step in enumerate(steps):
        dest = os.path.join(clips_dir, f"step_{i:02d}.mp4")
        keyword = step.get("visual_keyword", "hands working diy project")
        min_dur = max(step.get("duration_hint", 3), 3)
        try:
            fetch_pexels_clip(keyword, dest, min_duration=min_dur)
            results.append(dest)
        except Exception as e:
            logger.error(f"Pexels fetch failed step {i} ({keyword!r}): {e}")
            results.append(None)
    return results
