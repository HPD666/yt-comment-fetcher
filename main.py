import os
import re
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

VIDEO_ID = "Hume-QrkErs"
MAX_CHARS = 200
CACHE_FILE = "daily_sub_cache.json"

CLIENT_ID = os.environ.get("YT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

def get_authenticated_service():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        raise ValueError("GitHub Secrets (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN) missing.")

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

def get_daily_sub_gain(current_subs):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    start_subs = current_subs

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today:
                    start_subs = data.get("start_subs", current_subs)
                else:
                    start_subs = current_subs
        except Exception:
            start_subs = current_subs

    with open(CACHE_FILE, "w") as f:
        json.dump({"date": today, "start_subs": start_subs}, f)

    gain = current_subs - start_subs
    return f"+{gain}" if gain >= 0 else str(gain)

def update_video_and_get_comment():
    youtube = get_authenticated_service()

    comment_response = youtube.commentThreads().list(
        part="snippet", videoId=VIDEO_ID, order="time", textFormat="plainText", maxResults=1
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

    video_response = youtube.videos().list(part="snippet,statistics", id=VIDEO_ID).execute()
    if not video_response.get("items"):
        return {"status": "error"}

    video_snippet = video_response["items"][0]["snippet"]
    stats = video_response["items"][0].get("statistics", {})

    views = stats.get("viewCount", "0")
    likes = stats.get("likeCount", "0")
    total_comments = stats.get("commentCount", "0")

    channel_response = youtube.channels().list(part="statistics", id=video_snippet.get("channelId")).execute()
    daily_subs = "N/A"
    if channel_response.get("items"):
        total_subs = int(channel_response["items"][0]["statistics"].get("subscriberCount", 0))
        daily_subs = get_daily_sub_gain(total_subs)

    new_title = f"New Comment from {author}! Read Description ⬇️"
    if len(new_title) > 100:
        new_title = new_title[:97] + "..."

    current_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    new_description = f"""💬 LATEST PUBLIC COMMENT:
"{sanitized_text}"

— Commented by: {author}
— Posted at: {published_at}

📊 LIVE VIDEO & DAILY STATS:
— Views: {views}
— Likes: {likes}
— Total Comments: {total_comments}
— Today's New Subscribers: {daily_subs}

⏱️ SYSTEM INFO:
— Refresh Interval: Updated every 15 minutes
— Last Synced: {current_utc}

----------------------------------------
👍 Enjoyed this video?
- Leave a comment below to see your name & comment featured live!
- Don't forget to LIKE the video and SUBSCRIBE for more live interactive Shorts!
----------------------------------------
"""

    if video_snippet["title"] != new_title or video_snippet["description"] != new_description:
        video_snippet["title"] = new_title
        video_snippet["description"] = new_description
        youtube.videos().update(part="snippet", body={"id": VIDEO_ID, "snippet": video_snippet}).execute()

    return {"status": "ok", "daily_subs": daily_subs}

if __name__ == "__main__":
    result = update_video_and_get_comment()
    with open("latest_comment.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
