import logging
import time
from pathlib import Path
import requests
import fal_client
from config import config

logger = logging.getLogger(__name__)

KOKORO_RETRIES = 4
KOKORO_RETRY_DELAY = 8  # seconds between retries


def _save_bytes(data: bytes, path: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def synthesize_elevenlabs(text: str, output_path: str) -> str:
    from elevenlabs import ElevenLabs
    client = ElevenLabs(api_key=config.eleven_api_key)

    audio_generator = client.text_to_speech.convert(
        voice_id=config.eleven_voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            if chunk:
                f.write(chunk)

    logger.info(f"ElevenLabs → {output_path}")
    return output_path


def synthesize_kokoro(text: str, output_path: str) -> str:
    last_error = None
    for attempt in range(1, KOKORO_RETRIES + 1):
        try:
            result = fal_client.run(
                "fal-ai/kokoro/american-english",
                arguments={"prompt": text, "voice": "af_heart"},
            )
            audio_url = result["audio"]["url"]
            response = requests.get(audio_url, timeout=60)
            response.raise_for_status()
            _save_bytes(response.content, output_path)
            logger.info(f"Kokoro → {output_path}")
            return output_path
        except Exception as e:
            last_error = e
            if attempt < KOKORO_RETRIES:
                logger.warning(f"Kokoro attempt {attempt}/{KOKORO_RETRIES} failed: {e} — retrying in {KOKORO_RETRY_DELAY}s")
                time.sleep(KOKORO_RETRY_DELAY)
            else:
                logger.error(f"Kokoro failed after {KOKORO_RETRIES} attempts")

    raise RuntimeError(f"Kokoro TTS unavailable after {KOKORO_RETRIES} attempts: {last_error}")


def synthesize(text: str, output_path: str, virality_score: int) -> str:
    # Only attempt ElevenLabs if voice ID is set AND it's a high-score video
    use_elevenlabs = (
        virality_score >= config.tts_score_threshold
        and bool(config.eleven_voice_id)
        and bool(config.eleven_api_key)
    )

    if use_elevenlabs:
        try:
            return synthesize_elevenlabs(text, output_path)
        except Exception as e:
            logger.warning(f"ElevenLabs failed, falling back to Kokoro: {e}")

    return synthesize_kokoro(text, output_path)
