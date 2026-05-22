#!/usr/bin/env python3
"""
Test FFmpeg assembly on existing clips — no API calls, no money spent.
Trims/loops each clip to an equal share of the audio duration.

Usage:
  python test_assembler.py <folder_id>
  python test_assembler.py 6a378a5d
"""
import glob
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_assembler")

from pipeline.assembler import assemble_final, get_audio_duration


def test(folder_id: str):
    base = os.path.join("output", folder_id)
    audio = os.path.join(base, "voice.mp3")
    clips = sorted(glob.glob(os.path.join(base, "clips", "clip_*.mp4")))
    sub = os.path.join(base, "captions.ass")
    if not os.path.exists(sub):
        sub = os.path.join(base, "captions.srt")
    if not os.path.exists(sub):
        sub = None

    logger.info(f"Folder : {base}")
    logger.info(f"Audio  : {audio} — exists={os.path.exists(audio)}")
    logger.info(f"Clips  : {clips}")
    logger.info(f"Subs   : {sub}")

    if not os.path.exists(audio):
        logger.error("voice.mp3 not found")
        return
    if not clips:
        logger.error("No clips found in clips/")
        return

    audio_dur = get_audio_duration(audio)
    clip_dur = audio_dur / len(clips)
    durations = [clip_dur] * len(clips)
    logger.info(f"Audio {audio_dur:.1f}s / {len(clips)} clips = {clip_dur:.2f}s each")

    output = os.path.join(base, "final.mp4")
    assemble_final(clips, durations, audio, sub, output)
    logger.info(f"SUCCESS → {output}")
    logger.info(f"Open it: open '{output}'")


if __name__ == "__main__":
    folder_id = sys.argv[1] if len(sys.argv) > 1 else "6a378a5d"
    test(folder_id)
