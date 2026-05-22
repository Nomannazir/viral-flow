import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # fal.ai
    fal_key: str = field(default_factory=lambda: os.getenv("FAL_KEY", ""))

    # ElevenLabs
    eleven_api_key: str = field(default_factory=lambda: os.getenv("ELEVEN_API_KEY", ""))
    eleven_voice_id: str = field(default_factory=lambda: os.getenv("ELEVEN_VOICE_ID", ""))

    # Pexels
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", ""))

    # Reddit
    reddit_client_id: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    reddit_client_secret: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))

    # YouTube
    youtube_credentials_file: str = field(
        default_factory=lambda: os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials.json")
    )

    # Pipeline
    niche: str = field(default_factory=lambda: os.getenv("NICHE", "finance"))
    platform: str = field(default_factory=lambda: os.getenv("PLATFORM", "youtube"))
    video_duration: int = field(default_factory=lambda: int(os.getenv("VIDEO_DURATION", "45")))
    videos_per_run: int = field(default_factory=lambda: int(os.getenv("VIDEOS_PER_RUN", "3")))
    tts_score_threshold: int = field(default_factory=lambda: int(os.getenv("TTS_SCORE_THRESHOLD", "8")))

    # Cost controls
    max_daily_fal_spend: float = field(
        default_factory=lambda: float(os.getenv("MAX_DAILY_FAL_SPEND", "8.0"))
    )

    # Audio — drop MP3/M4A files in the music/ folder for background music
    music_dir: str = field(default_factory=lambda: os.getenv("MUSIC_DIR", "music"))
    use_voiceover: bool = field(
        default_factory=lambda: os.getenv("USE_VOICEOVER", "true").lower() == "true"
    )

    # Output
    output_dir: str = field(default_factory=lambda: os.getenv("OUTPUT_DIR", "./output"))


config = Config()

# fal.ai SDK reads FAL_KEY from environment
if config.fal_key:
    os.environ["FAL_KEY"] = config.fal_key
