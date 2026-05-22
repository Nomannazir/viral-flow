import json
import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

VID_W, VID_H = 1080, 1920

_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


# ── Font loading ───────────────────────────────────────────────────────────────

def _load_font(size: int):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Text overlay rendering ─────────────────────────────────────────────────────

def _render_text_overlay(
    top_text: str,
    bottom_text: str,
    output_path: str,
    width: int = VID_W,
    height: int = VID_H,
) -> Optional[str]:
    """Render a transparent full-frame PNG with a top label and bottom instruction."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed — text overlays disabled. Run: pip install Pillow")
        return None

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _draw_pill(text: str, font, y_center: int) -> None:
        if not text or font is None:
            return
        tmp_img = Image.new("RGBA", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)
        max_w = width - 80
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = tmp_draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_w and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        bboxes = [tmp_draw.textbbox((0, 0), ln, font=font) for ln in lines]
        widths = [b[2] - b[0] for b in bboxes]
        heights = [b[3] - b[1] for b in bboxes]
        gap = 10
        total_h = sum(heights) + gap * (len(lines) - 1)
        pad_x, pad_y = 32, 20
        box_w = max(widths) + pad_x * 2
        box_h = total_h + pad_y * 2
        box_x = (width - box_w) // 2
        box_y = y_center - box_h // 2

        draw.rounded_rectangle(
            [box_x, box_y, box_x + box_w, box_y + box_h],
            radius=18, fill=(0, 0, 0, 185),
        )

        y = box_y + pad_y
        stroke = 4
        for ln, lw, lh in zip(lines, widths, heights):
            x = (width - lw) // 2
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    if dx or dy:
                        draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
            y += lh + gap

    if top_text:
        _draw_pill(top_text.upper(), _load_font(72), y_center=120)
    if bottom_text:
        _draw_pill(bottom_text, _load_font(56), y_center=height - 190)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{result.stderr[-500:]}")


def _image_to_video(img_path: str, duration: float, output_path: str) -> str:
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_path,
        "-t", str(duration),
        "-vf", f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=increase,crop={VID_W}:{VID_H}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an", output_path,
    ], "image_to_video")
    return output_path


def _trim_clip(clip_path: str, duration: float, output_path: str) -> str:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", clip_path],
        capture_output=True, text=True, check=True,
    )
    src_dur = float(json.loads(probe.stdout)["format"]["duration"])

    loop_file = None
    if src_dur >= duration:
        cmd = [
            "ffmpeg", "-y", "-i", clip_path, "-t", str(duration),
            "-vf", f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=increase,crop={VID_W}:{VID_H}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path,
        ]
    else:
        loops = int(duration / src_dur) + 2
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for _ in range(loops):
                f.write(f"file '{os.path.abspath(clip_path)}'\n")
            loop_file = f.name
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", loop_file,
            "-t", str(duration),
            "-vf", f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=increase,crop={VID_W}:{VID_H}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path,
        ]

    try:
        _run(cmd, "trim_clip")
    finally:
        if loop_file:
            try:
                os.unlink(loop_file)
            except OSError:
                pass
    return output_path


def _overlay_png(video_path: str, png_path: str, output_path: str) -> str:
    _run([
        "ffmpeg", "-y",
        "-i", video_path, "-i", png_path,
        "-filter_complex", "[0:v][1:v]overlay=0:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an", output_path,
    ], "overlay_png")
    return output_path


def _concatenate(segment_paths: list[str], output_path: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in segment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        concat_file = f.name
    try:
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path,
        ], "concatenate")
    finally:
        try:
            os.unlink(concat_file)
        except OSError:
            pass
    return output_path


def _add_audio(
    video_path: str,
    audio_path: Optional[str],
    music_path: Optional[str],
    output_path: str,
) -> str:
    if not audio_path and not music_path:
        _run(["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path], "copy_video")
        return output_path

    inputs = ["-i", video_path]
    filter_parts: list[str] = []
    audio_map: str = ""

    if audio_path and music_path:
        inputs += ["-i", audio_path, "-i", music_path]
        filter_parts = [
            "[2:a]volume=0.15[music]",
            "[1:a][music]amix=inputs=2:duration=first[out]",
        ]
        audio_map = "[out]"
    elif audio_path:
        inputs += ["-i", audio_path]
        audio_map = "1:a"
    else:
        inputs += ["-i", music_path]
        audio_map = "1:a"

    cmd = ["ffmpeg", "-y"] + inputs
    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts), "-map", "0:v", "-map", audio_map]
    else:
        cmd += ["-map", "0:v", "-map", audio_map]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", output_path]

    _run(cmd, "add_audio")
    return output_path


def _pick_music() -> Optional[str]:
    music_dir = getattr(config, "music_dir", "music")
    if not music_dir or not os.path.isdir(music_dir):
        return None
    files = [
        f for f in os.listdir(music_dir)
        if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac"))
    ]
    return os.path.join(music_dir, random.choice(files)) if files else None


# ── Main entry point ───────────────────────────────────────────────────────────

def build_video(
    storyboard: dict,
    output_dir: str,
    step_clips: list,
    before_img: str,
    after_img: str,
    audio_path: Optional[str] = None,
) -> dict:
    """
    Assemble a DIY viral short from storyboard + pre-fetched assets.

    Segment order:
      before hook (1.5s) → after reveal (1.5s) → 5 steps → final reveal (2.5s) → CTA (2s)
    Each segment gets bold text overlays via Pillow PNGs burned in by FFmpeg.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    seg_dir = os.path.join(output_dir, "segments")
    ov_dir = os.path.join(output_dir, "overlays")
    Path(seg_dir).mkdir(exist_ok=True)
    Path(ov_dir).mkdir(exist_ok=True)

    music_path = _pick_music()
    if music_path:
        logger.info(f"Background music: {os.path.basename(music_path)}")

    steps = storyboard.get("steps", [])

    segments = [
        {
            "source": before_img, "type": "image", "duration": 1.5,
            "top": storyboard.get("hook_text", "BEFORE"), "bottom": "",
        },
        {
            "source": after_img, "type": "image", "duration": 1.5,
            "top": "AFTER ✅", "bottom": "Here's how →",
        },
    ]

    last_good_clip = None
    for step, clip in zip(steps, step_clips):
        if clip and os.path.exists(clip):
            last_good_clip = clip
        source = last_good_clip or before_img
        s_type = "video" if (clip and os.path.exists(clip)) else "image"
        segments.append({
            "source": source, "type": s_type,
            "duration": max(step.get("duration_hint", 4), 2),
            "top": f"STEP {step['number']}", "bottom": step.get("on_screen_text", ""),
        })

    segments.append({
        "source": after_img, "type": "image", "duration": 2.5,
        "top": storyboard.get("reveal_text", ""), "bottom": "",
    })
    segments.append({
        "source": after_img, "type": "image", "duration": 2.0,
        "top": "", "bottom": storyboard.get("cta_text", "Save this!"),
    })

    processed: list[str] = []
    for idx, seg in enumerate(segments):
        raw = os.path.join(seg_dir, f"raw_{idx:02d}.mp4")
        overlaid = os.path.join(seg_dir, f"seg_{idx:02d}.mp4")
        ov_png = os.path.join(ov_dir, f"ov_{idx:02d}.png")

        logger.info(f"Segment {idx}: [{seg['type']}] {seg['top']!r} / {seg['bottom']!r}")
        try:
            if seg["type"] == "image":
                _image_to_video(seg["source"], seg["duration"], raw)
            else:
                _trim_clip(seg["source"], seg["duration"], raw)

            png = _render_text_overlay(seg["top"], seg["bottom"], ov_png)
            target = overlaid if png else raw
            if png:
                _overlay_png(raw, png, overlaid)
            processed.append(target)
        except Exception as e:
            logger.error(f"Segment {idx} failed: {e}")
            if processed:
                processed.append(processed[-1])

    if not processed:
        raise RuntimeError("No segments assembled — cannot build video")

    silent = os.path.join(output_dir, "silent.mp4")
    _concatenate(processed, silent)

    final_path = os.path.join(output_dir, "final.mp4")
    _add_audio(silent, audio_path, music_path, final_path)

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", final_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    logger.info(f"Video assembled: {final_path} ({duration:.1f}s)")

    return {"video_path": final_path, "duration": duration}
