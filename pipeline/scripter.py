import json
import logging
import re
from typing import Optional
from anthropic import Anthropic
from config import config

logger = logging.getLogger(__name__)
_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.anthropic_api_key)
    return _client


STORYBOARD_SYSTEM = """You are a viral short video director for a DIY & Home Hacks channel.
Output ONLY valid JSON — no markdown, no text outside the JSON object.

Format: YouTube Shorts / TikTok (9:16 vertical, 30–55 seconds total)
Style: Text-overlay-first. Visuals SHOW the transformation. Text IS the content.
Energy: Fast cuts, satisfying reveals, "I need to try this right now" reaction.

Structure (ALWAYS follow this arc):
1. Hook (0–2s): Tease the end result — viewer must keep watching
2. Steps (5 steps): One clear physical action per step
3. Reveal (final 3s): Finished result + cost or time saved + CTA

Rules for steps:
- on_screen_text: max 6 words, punchy, title-case — this is what viewers READ on screen
- visual_keyword: 3–5 words for stock video search — describe what HANDS or OBJECTS are doing
  GOOD: "hands arranging bins on shelf", "spray painting wooden chair", "cutting fabric scissors"
  BAD: "transformation", "before and after", "diy project" (too vague for stock search)
- duration_hint: seconds per step (2–5s each — these are SHORT videos)
- voiceover_line: optional spoken line — only write it if the step genuinely needs explaining.
  Many viral DIY videos have NO voiceover. Omit the key entirely if not needed.

Rules for images:
- hook_visual_before: the PROBLEM state — messy, broken, ugly, frustrating
  Example: "cluttered pantry with mismatched containers spilling everywhere, harsh overhead light"
- hook_visual_after: the RESULT state — beautiful, organized, satisfying, aspirational
  Example: "perfectly organized pantry with matching white bins and labels, warm natural light"
- Photorealistic and specific. No text, no logos, no people's faces.

Output format (all fields required):
{
  "title": "YouTube title with hook keyword, under 60 chars",
  "description": "150-word SEO description with relevant keywords",
  "hashtags": ["#diy", "#hack", "#homeimprovement", "#organization", "#lifehack"],
  "thumbnail_prompt": "dramatic before/after split scene, photorealistic, bright colors, no text",
  "hook_visual_before": "FLUX image prompt — problem state, photorealistic, specific, vertical",
  "hook_visual_after": "FLUX image prompt — beautiful result, photorealistic, specific, vertical",
  "hook_text": "3–5 word hook shown on first frame (e.g. BEFORE THIS HACK)",
  "steps": [
    {
      "number": 1,
      "on_screen_text": "max 6 words shown on screen",
      "visual_keyword": "3–5 words for pexels stock video search",
      "duration_hint": 4
    }
  ],
  "reveal_text": "final overlay — cost, time, or wow factor (e.g. Total cost: $4)",
  "cta_text": "save this or follow for more (max 5 words)"
}

Generate exactly 5 steps. Every visual_keyword must describe a physical action, not an abstract concept."""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_storyboard(topic: str, hook_type: str, virality_score: int) -> dict:
    model = "claude-sonnet-4-6" if virality_score >= 8 else "claude-haiku-4-5-20251001"
    logger.info(f"Storyboard with {model} (score {virality_score}/10)")

    user_msg = (
        f"Topic: {topic}\n"
        f"Virality score: {virality_score}/10\n"
        f"Hook type: {hook_type}\n\n"
        f"Create a storyboard for a viral DIY short video on this topic. "
        f"Use the '{hook_type}' hook style to open the video."
    )

    response = _get_client().messages.create(
        model=model,
        max_tokens=2048,
        system=STORYBOARD_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = _strip_markdown(response.content[0].text)
    try:
        storyboard = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Storyboard JSON parse failed:\n{raw[:500]}")
        raise ValueError(f"Claude returned invalid JSON: {e}") from e

    storyboard["model_used"] = model
    storyboard["topic"] = topic
    return storyboard
