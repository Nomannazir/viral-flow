#!/usr/bin/env python3
"""
ViralFlow orchestrator — runs the full DIY video pipeline end to end.

Usage:
  python orchestrator.py                    # fetch trends → produce videos → publish
  python orchestrator.py --dry-run          # score topics + print storyboard only
  python orchestrator.py --topic "..."      # skip trend fetch, use this specific topic
  python orchestrator.py --videos 1         # override VIDEOS_PER_RUN
  python orchestrator.py --no-publish       # assemble video but skip YouTube upload
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

USED_TOPICS_FILE = "used_topics.json"


def _load_used_topics() -> set:
    used = set()
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE) as f:
            used.update(json.load(f))
    output_dir = "output"
    if os.path.isdir(output_dir):
        for folder in os.scandir(output_dir):
            meta = os.path.join(folder.path, "metadata.json")
            if os.path.exists(meta):
                with open(meta) as f:
                    data = json.load(f)
                    if "topic" in data:
                        used.add(data["topic"].lower().strip())
    return used


def _save_used_topic(topic: str, video_id: str, out_dir: str, extra: dict = None) -> None:
    used = _load_used_topics()
    used.add(topic.lower().strip())
    with open(USED_TOPICS_FILE, "w") as f:
        json.dump(sorted(used), f, indent=2)
    meta = {"topic": topic, "video_id": video_id, **(extra or {})}
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)


def _extract_voiceover(storyboard: dict) -> str:
    """Collect per-step voiceover lines into one continuous narration."""
    lines = [
        step["voiceover_line"]
        for step in storyboard.get("steps", [])
        if step.get("voiceover_line")
    ]
    return " ".join(lines)


def _print_storyboard_summary(storyboard: dict) -> None:
    print("\n" + "─" * 55)
    print(f"TITLE  : {storyboard.get('title')}")
    print(f"HOOK   : {storyboard.get('hook_text')}")
    for step in storyboard.get("steps", []):
        print(f"STEP {step['number']} : {step.get('on_screen_text')}  [{step.get('visual_keyword')}]")
    print(f"REVEAL : {storyboard.get('reveal_text')}")
    print(f"CTA    : {storyboard.get('cta_text')}")
    print(f"MODEL  : {storyboard.get('model_used')}")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")

from config import config
from db.client import db
from pipeline.trends import fetch_trending_topics
from pipeline.scorer import score_topics
from pipeline.scripter import generate_storyboard
from pipeline.voice import synthesize
from pipeline.visuals import generate_flux_image, fetch_clips_for_steps, generate_thumbnail
from pipeline.assembler import build_video
from pipeline.publisher import upload_to_youtube


def run_pipeline(
    dry_run: bool = False,
    topic_override: Optional[str] = None,
    videos: Optional[int] = None,
    no_publish: bool = False,
):
    n_videos = videos or config.videos_per_run

    logger.info("=" * 60)
    logger.info("ViralFlow DIY pipeline starting")
    logger.info(f"Niche: {config.niche} | Platform: {config.platform} | Videos: {n_videos}")
    if dry_run:
        logger.info("DRY RUN — storyboard only, no media generation")
    logger.info("=" * 60)

    # ── 1. Topics ──────────────────────────────────────────────────────────────
    if topic_override:
        raw_topics = [{"topic": topic_override, "source": "manual", "score_hint": 8}]
    else:
        logger.info("Fetching trending DIY topics...")
        raw_topics = fetch_trending_topics(limit=50)
        logger.info(f"Fetched {len(raw_topics)} raw topics")

        used = _load_used_topics()
        before = len(raw_topics)
        raw_topics = [t for t in raw_topics if t["topic"].lower().strip() not in used]
        if before - len(raw_topics):
            logger.info(f"Skipped {before - len(raw_topics)} already-produced topics")

    logger.info("Scoring topics with Claude Haiku...")
    topics = score_topics(raw_topics, min_score=6)

    if not topics:
        logger.warning("No topics passed the score threshold. Exiting.")
        return

    logger.info(f"{len(topics)} topics passed — processing top {n_videos}")

    # ── Process each topic ─────────────────────────────────────────────────────
    for topic_data in topics[:n_videos]:
        video_id = str(uuid.uuid4())[:8]
        out_dir = os.path.join(config.output_dir, video_id)
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        topic = topic_data["topic"]
        score = topic_data.get("virality_score", topic_data.get("score_hint", 7))
        hook_type = topic_data.get("hook_type", "before_after")

        logger.info(f"\n{'─' * 50}")
        logger.info(f"Topic : {topic[:70]}")
        logger.info(f"Score : {score}/10  Hook: {hook_type}  ID: {video_id}")

        try:
            # ── 2. Storyboard ──────────────────────────────────────────────────
            logger.info("Generating storyboard...")
            storyboard = generate_storyboard(topic, hook_type, score)
            logger.info(f"Title : {storyboard['title']}")
            logger.info(f"Hook  : {storyboard['hook_text']}")

            if dry_run:
                _print_storyboard_summary(storyboard)
                continue

            # ── 3. Before / after FLUX images ──────────────────────────────────
            before_img = os.path.join(out_dir, "before.jpg")
            after_img = os.path.join(out_dir, "after.jpg")
            logger.info("Generating before/after images with FLUX...")
            generate_flux_image(storyboard["hook_visual_before"], before_img)
            generate_flux_image(storyboard["hook_visual_after"], after_img)

            # ── 4. Thumbnail ───────────────────────────────────────────────────
            thumb_path = os.path.join(out_dir, "thumbnail.jpg")
            try:
                logger.info("Generating thumbnail...")
                generate_thumbnail(storyboard["thumbnail_prompt"], thumb_path)
            except Exception as e:
                logger.warning(f"Thumbnail failed (using after image): {e}")
                thumb_path = after_img

            # ── 5. Stock clips from Pexels ─────────────────────────────────────
            clips_dir = os.path.join(out_dir, "clips")
            logger.info(f"Fetching {len(storyboard['steps'])} Pexels stock clips...")
            step_clips = fetch_clips_for_steps(storyboard["steps"], clips_dir)
            succeeded = sum(1 for c in step_clips if c)
            logger.info(f"Clips ready: {succeeded}/{len(step_clips)}")

            # ── 6. Optional voiceover ──────────────────────────────────────────
            audio_path = None
            if getattr(config, "use_voiceover", True):
                voiceover_text = _extract_voiceover(storyboard)
                if voiceover_text:
                    audio_path = os.path.join(out_dir, "voice.mp3")
                    logger.info("Synthesizing voiceover...")
                    try:
                        synthesize(voiceover_text, audio_path, score)
                    except Exception as e:
                        logger.warning(f"Voice failed (music only): {e}")
                        audio_path = None

            # ── 7. Assemble ────────────────────────────────────────────────────
            logger.info("Assembling video...")
            result = build_video(storyboard, out_dir, step_clips, before_img, after_img, audio_path)
            logger.info(f"Video ready: {result['video_path']} ({result['duration']:.1f}s)")

            # ── 8. Publish ─────────────────────────────────────────────────────
            publish_result = {"video_id": None, "url": None}
            if not no_publish:
                logger.info("Uploading to YouTube...")
                publish_result = upload_to_youtube(result["video_path"], thumb_path, storyboard)

            # ── 9. Persist ─────────────────────────────────────────────────────
            _save_used_topic(topic, video_id, out_dir, extra={
                "title": storyboard["title"],
                "youtube_url": publish_result.get("url"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            if db:
                try:
                    db.table("videos").insert({
                        "id": video_id,
                        "topic": topic,
                        "virality_score": score,
                        "title": storyboard["title"],
                        "youtube_url": publish_result.get("url"),
                        "youtube_video_id": publish_result.get("video_id"),
                        "status": "published" if publish_result.get("url") else "assembled",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                except Exception as e:
                    logger.warning(f"Supabase insert failed (non-fatal): {e}")

            if publish_result.get("url"):
                logger.info(f"Published: {publish_result['url']}")
            else:
                logger.info(f"Video saved locally: {result['video_path']}")

        except Exception as e:
            logger.error(f"Pipeline failed for topic '{topic[:60]}': {e}", exc_info=True)
            continue

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline run complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ViralFlow DIY pipeline runner")
    parser.add_argument("--dry-run", action="store_true", help="Storyboard only — no media, no upload")
    parser.add_argument("--topic", type=str, help="Skip trend fetch and use this specific topic")
    parser.add_argument("--videos", type=int, help="Number of videos to produce this run")
    parser.add_argument("--no-publish", action="store_true", help="Assemble video but skip YouTube upload")
    args = parser.parse_args()

    run_pipeline(
        dry_run=args.dry_run,
        topic_override=args.topic,
        videos=args.videos,
        no_publish=args.no_publish,
    )
