import logging
from datetime import datetime, timedelta, timezone

from config import config

logger = logging.getLogger(__name__)

DIY_SUBREDDITS = [
    "DIY", "lifehacks", "organization", "HomeImprovement",
    "thrifting", "CleaningTips", "Frugal", "gardening",
]

_YT_DIY_QUERIES = [
    "diy home hack",
    "organization hack dollar store",
    "thrift flip transformation",
    "cleaning hack before after",
    "home improvement budget",
    "satisfying diy project",
    "life hack that actually works",
    "room makeover before after",
]

FALLBACK_DIY_TOPICS = [
    {"topic": "Transform cluttered pantry with $5 dollar store bins", "source": "fallback", "score_hint": 8},
    {"topic": "Thrift store chair becomes designer piece with $10 spray paint", "source": "fallback", "score_hint": 9},
    {"topic": "Dead plants revived with this one watering trick", "source": "fallback", "score_hint": 7},
    {"topic": "Bathroom glow up under $30 with peel-and-stick tiles", "source": "fallback", "score_hint": 8},
    {"topic": "Messy cable nightmare fixed for $3 at dollar store", "source": "fallback", "score_hint": 8},
    {"topic": "Remove scratches from wood furniture with olive oil and vinegar", "source": "fallback", "score_hint": 8},
    {"topic": "Closet space doubled with vertical tension rods", "source": "fallback", "score_hint": 9},
    {"topic": "Greasy stovetop cleaned in 5 minutes with baking soda paste", "source": "fallback", "score_hint": 8},
    {"topic": "Ugly plastic planters turned terracotta with chalk paint", "source": "fallback", "score_hint": 8},
    {"topic": "Fruit flies eliminated overnight with this kitchen hack", "source": "fallback", "score_hint": 9},
    {"topic": "Scuffed white sneakers restored to brand new in 10 minutes", "source": "fallback", "score_hint": 8},
    {"topic": "Fridge organization system that actually lasts all month", "source": "fallback", "score_hint": 8},
    {"topic": "Shower mold removed without scrubbing using one ingredient", "source": "fallback", "score_hint": 9},
    {"topic": "Plain walls transformed with paint tape geometric pattern for $5", "source": "fallback", "score_hint": 8},
    {"topic": "Bathroom mirror framed with dollar store molding strips", "source": "fallback", "score_hint": 8},
    {"topic": "Turn old t-shirts into reusable cleaning rags in 5 minutes", "source": "fallback", "score_hint": 7},
    {"topic": "Condensation on windows fixed permanently with $4 trick", "source": "fallback", "score_hint": 7},
    {"topic": "Ugly rental kitchen transformed with removable contact paper", "source": "fallback", "score_hint": 8},
    {"topic": "Garage wall organized with pegboard system for $15", "source": "fallback", "score_hint": 7},
    {"topic": "Kitchen drawer organizer built from cardboard boxes", "source": "fallback", "score_hint": 7},
    {"topic": "Old wine bottles upcycled into decorative vases", "source": "fallback", "score_hint": 7},
    {"topic": "Under-sink cabinet organizer built for $8", "source": "fallback", "score_hint": 8},
    {"topic": "Broken zipper fixed in 30 seconds without replacing it", "source": "fallback", "score_hint": 7},
    {"topic": "Towel organization hack using magazine holders", "source": "fallback", "score_hint": 7},
    {"topic": "Laundry room wall turned functional with tension rod shelves", "source": "fallback", "score_hint": 8},
]


def get_youtube_trending_topics(limit: int = 25) -> list[dict]:
    try:
        from pipeline.publisher import _get_youtube_client
        yt = _get_youtube_client()
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        video_ids = []
        titles_by_id = {}

        for query in _YT_DIY_QUERIES[:4]:
            try:
                resp = yt.search().list(
                    part="snippet", q=query, type="video",
                    videoDuration="short", order="viewCount",
                    publishedAfter=published_after, maxResults=8, regionCode="US",
                ).execute()
                for item in resp.get("items", []):
                    vid_id = item["id"]["videoId"]
                    if vid_id not in titles_by_id:
                        video_ids.append(vid_id)
                        titles_by_id[vid_id] = item["snippet"]["title"]
            except Exception as e:
                logger.warning(f"YouTube search failed for '{query}': {e}")

        if not video_ids:
            return []

        stats = yt.videos().list(
            part="statistics", id=",".join(video_ids[:50])
        ).execute()
        stats_by_id = {
            item["id"]: int(item["statistics"].get("viewCount", 0))
            for item in stats.get("items", [])
        }

        topics = []
        for vid_id, title in titles_by_id.items():
            views = stats_by_id.get(vid_id, 0)
            if views < 5_000:
                continue
            score_hint = min(10, max(6, 6 + int(views / 300_000)))
            topics.append({
                "topic": title,
                "source": "youtube_trending",
                "score_hint": score_hint,
                "views": views,
            })

        topics.sort(key=lambda x: x["views"], reverse=True)
        logger.info(f"YouTube trending: {len(topics)} topics")
        return topics[:limit]
    except Exception as e:
        logger.warning(f"YouTube trending unavailable: {e}")
        return []


def get_reddit_topics(limit: int = 12) -> list[dict]:
    if not config.reddit_client_id or not config.reddit_client_secret:
        return []
    try:
        import praw
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            user_agent="viralflow/1.0 (diy content pipeline)",
        )
        topics = []
        for sub in DIY_SUBREDDITS[:4]:
            for post in reddit.subreddit(sub).hot(limit=6):
                if post.score > 100 and not post.stickied:
                    topics.append({
                        "topic": post.title,
                        "source": f"reddit/r/{sub}",
                        "score_hint": min(int(post.score / 300), 10),
                        "upvotes": post.score,
                    })
        logger.info(f"Reddit: {len(topics)} topics")
        return topics[:limit]
    except Exception as e:
        logger.warning(f"Reddit unavailable: {e}")
        return []


def fetch_trending_topics(limit: int = 50) -> list[dict]:
    topics = []

    yt = get_youtube_trending_topics(limit=25)
    topics.extend(yt)

    topics.extend(get_reddit_topics(limit=12))

    if len(topics) < 10:
        logger.info("Insufficient live topics — using DIY evergreen fallback list")
        topics.extend(FALLBACK_DIY_TOPICS)

    seen: set[str] = set()
    unique = []
    for t in topics:
        key = t["topic"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(t)

    logger.info(f"Total unique topics: {len(unique)}")
    return unique[:limit]
