import json
import logging
import re
from typing import Optional
from anthropic import Anthropic, APIStatusError
from config import config

logger = logging.getLogger(__name__)
_client: Optional[Anthropic] = None

_HOOK_BY_KEYWORD = {
    "before": "before_after",
    "after": "before_after",
    "transform": "transformation",
    "thrift": "transformation",
    "flip": "transformation",
    "upcycl": "transformation",
    "hack": "problem_solved",
    "fix": "problem_solved",
    "clean": "problem_solved",
    "remov": "problem_solved",
    "trick": "secret_trick",
    "secret": "secret_trick",
    "nobody": "secret_trick",
    "viral": "challenge",
    "tried": "challenge",
    "5 ": "problem_solved",
    "3 ": "problem_solved",
    "$": "before_after",
    "organiz": "before_after",
    "glow up": "before_after",
}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.anthropic_api_key)
    return _client


def _guess_hook_type(topic: str) -> str:
    lower = topic.lower()
    for keyword, hook in _HOOK_BY_KEYWORD.items():
        if keyword in lower:
            return hook
    return "before_after"


SCORER_SYSTEM = """You are a viral content strategist for DIY & Home Hacks short videos.
Score the given topic for virality on YouTube Shorts / TikTok (1–10 scale).
Output ONLY valid JSON — no markdown, no explanation outside the JSON.

Scoring criteria:
- Transformation potential: dramatic visible before vs after?
- Cost appeal: achievable under $20? Materials at dollar store or already at home?
- Beginner-friendly: can most people do this with no special skills or tools?
- Trending format: fits organization / thrift flip / cleaning hack / before-after viral formats?
- Satisfaction factor: how visually satisfying is the process or result?

Hook types:
- before_after    → "Your [thing] before vs after this $X hack"
- problem_solved  → "Finally fix [annoying problem] in 5 minutes"
- transformation  → "Thrift store [item] → designer piece for $10"
- secret_trick    → "The [ingredient] trick nobody talks about"
- challenge       → "I tried the viral [hack] so you don't have to"

Output format:
{
  "score": 8,
  "hook_type": "before_after",
  "title": "punchy video title under 60 chars",
  "reasoning": "one sentence"
}"""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def score_topic(topic: str) -> dict:
    try:
        response = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=SCORER_SYSTEM,
            messages=[{"role": "user", "content": f"Topic: {topic}"}],
        )
        return json.loads(_strip_markdown(response.content[0].text))
    except APIStatusError as e:
        if e.status_code == 400 and "credit balance" in str(e):
            raise RuntimeError(
                "Anthropic API credit balance is zero. "
                "Add credits at console.anthropic.com → Plans & Billing."
            ) from e
        if e.status_code == 404:
            raise RuntimeError(f"Model not found: {e}") from e
        logger.warning(f"API error scoring '{topic[:50]}': {e}")
        return None
    except json.JSONDecodeError:
        logger.warning(f"Score JSON parse failed for: {topic[:60]}")
        return None
    except Exception as e:
        logger.warning(f"Scoring error for '{topic[:50]}': {e}")
        return None


def score_topics(topics: list[dict], min_score: int = 6) -> list[dict]:
    passed = []
    claude_available = True

    for t in topics:
        if claude_available:
            try:
                result = score_topic(t["topic"])
            except RuntimeError as e:
                logger.warning(f"Switching to fallback scoring: {e}")
                claude_available = False
                result = None
        else:
            result = None

        if result is not None:
            t.update({
                "virality_score": result["score"],
                "hook_type": result["hook_type"],
                "video_title": result["title"],
            })
        else:
            score = t.get("score_hint", 7)
            t.update({
                "virality_score": score,
                "hook_type": _guess_hook_type(t["topic"]),
                "video_title": t["topic"][:60],
            })

        status = "PASS" if t["virality_score"] >= min_score else "skip"
        source = "claude" if result else "fallback"
        logger.info(f"[{t['virality_score']}/10] [{status}] [{source}] {t['topic'][:60]}")

        if t["virality_score"] >= min_score:
            passed.append(t)

    if not claude_available:
        logger.warning(
            "Claude scoring unavailable — used score_hint values. "
            "Add Anthropic credits for AI-powered scoring."
        )

    return sorted(passed, key=lambda x: x["virality_score"], reverse=True)
