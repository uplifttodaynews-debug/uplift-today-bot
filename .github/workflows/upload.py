"""
upload.py - Step 5: upload the finished video to YouTube using your saved keys.
"""
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import config


def _service():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video_path, title, description, tags, thumb_path=None):
    yt = _service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags,
            "categoryId": "25",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": {
            "privacyStatus": config.PRIVACY,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # YouTube's AI-content disclosure
        },
    }
    media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
    except HttpError as e:
        if e.resp.status == 400 and "containsSyntheticMedia" in str(e):
            print("[upload] disclosure field rejected - retrying without it. "
                  "Please tick 'altered content' manually in YouTube Studio.")
            del body["status"]["containsSyntheticMedia"]
            media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
        else:
            raise
    vid = resp["id"]
    print(f"[upload] done: https://youtu.be/{vid} ({config.PRIVACY})")
    if thumb_path:
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
        except Exception as e:
            print(f"[upload] thumbnail skipped (channel may need phone verification): {e}")
    return vid
