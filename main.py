import os
import re
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

VIDEO_ID = "Hume-QrkErs"
MAX_CHARS = 200

CLIENT_ID = os.environ.get("YT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

def get_authenticated_service():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        raise ValueError("GitHub Secrets (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN) missing or unreadable.")

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
    )
    return build("youtube", "v3", credentials=creds)

def sanitize_text(text, max_chars=200):
    text = re.sub(r'https?://\S+|www\.\S+', '[link]', text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[email]', text)
    text = re.sub(r'\+?\d[\d\s-]{7,}\d', '[phone]', text)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + '…'
    return text.strip()

def contains_unsafe_content(text):
    unsafe_keywords = ['hate', 'threat', 'explicit', 'doxx']
    return any(word in text.lower() for word in unsafe_keywords)

def update_video_and_get_comment():
    youtube = get_authenticated_service()

    # 1. En son yorumu çek
    comment_response = youtube.commentThreads().list(
        part="snippet",
        videoId=VIDEO_ID,
        order="time",
        textFormat="plainText",
        maxResults=1
    ).execute()

    items = comment_response.get("items", [])
    if not items:
        return {"status": "empty"}

    top_comment = items[0]["snippet"]["topLevelComment"]["snippet"]
    raw_text = top_comment.get("textDisplay", "")
    author = top_comment.get("authorDisplayName", "Anonymous")
    published_at = top_comment.get("publishedAt", "")

    if contains_unsafe_content(raw_text):
        return {"status": "unsafe", "reason": "content policy"}

    sanitized_text = sanitize_text(raw_text, MAX_CHARS)
    
    # 2. Başlığı Açıklamaya Yönlendirecek Şekilde Ayarla
    new_title = f"New Comment from {author}! Read Description ⬇️"
    if len(new_title) > 100:
        new_title = new_title[:97] + "..."

    current_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # 3. Yorum Bilgisi ve Beğeni/Abone Çağrılı Açıklama Metni
    new_description = f"""💬 LATEST PUBLIC COMMENT:
"{sanitized_text}"

— Commented by: {author}
— Posted at: {published_at}
— Last Synced: {current_utc}

----------------------------------------
👍 Enjoyed this video?
- Leave a comment below to see your name & comment featured live in the description!
- Don't forget to LIKE the video and SUBSCRIBE for more live interactive Shorts!
----------------------------------------
"""

    # 4. Videonun mevcut bilgilerini al ve güncelle
    video_response = youtube.videos().list(
        part="snippet",
        id=VIDEO_ID
    ).execute()

    if video_response["items"]:
        video_snippet = video_response["items"][0]["snippet"]
        
        # Eğer başlık veya açıklama değiştiyse YouTube'da güncelle
        if video_snippet["title"] != new_title or video_snippet["description"] != new_description:
            video_snippet["title"] = new_title
            video_snippet["description"] = new_description
            
            youtube.videos().update(
                part="snippet",
                body={
                    "id": VIDEO_ID,
                    "snippet": video_snippet
                }
            ).execute()

    return {
        "status": "ok",
        "comment_text": sanitized_text,
        "author_display": author,
        "published_at": published_at,
        "updated_video_title": new_title,
        "last_updated_utc": current_utc
    }

if __name__ == "__main__":
    result = update_video_and_get_comment()
    json_output = json.dumps(result, indent=2, ensure_ascii=False)
    
    with open("latest_comment.json", "w", encoding="utf-8") as f:
        f.write(json_output)
        
    print(json_output)
