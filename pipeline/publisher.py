import logging
import os
import pickle
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_FILE = "youtube_token.pickle"


def _get_youtube_client():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.youtube_credentials_file):
                raise FileNotFoundError(
                    f"YouTube credentials file not found: {config.youtube_credentials_file}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(config.youtube_credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(video_path: str, thumbnail_path: Optional[str], script: dict) -> dict:
    youtube = _get_youtube_client()

    body = {
        "snippet": {
            "title": script["title"][:100],
            "description": script.get("description", ""),
            "tags": [t.lstrip("#") for t in script.get("hashtags", [])],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5 MB chunks
    )

    logger.info(f"Uploading: {script['title']}")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"Published: {url}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            logger.info("Thumbnail set")
        except Exception as e:
            logger.warning(f"Thumbnail upload failed: {e}")

    return {"video_id": video_id, "url": url}
