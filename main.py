import os
import re
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

VIDEO_ID = "Hume-QrkErs"
MAX_CHARS = 140
API_KEY = os.environ.get("YT_API_KEY")

def sanitize_text(text, max_chars=140):
    text = re.sub(r'https?://\S+|www\.\S+', '[link]', text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[email]', text)
    text = re.sub(r'\+?\d[\d\s-]{7,}\d', '[phone]', text)
    
    if len(text) > max_chars:
        truncated = text[:max_chars].rsplit(' ', 1)[0]
        text = truncated + '…'
        
    return text.strip()

def contains_unsafe_content(text):
    unsafe_keywords = ['hate', 'threat', 'explicit', 'doxx'] 
    return any(word in text.lower() for word in unsafe_keywords)

def get_latest_comment():
    if not API_KEY:
        return {"status": "error", "notes": "Missing YT_API_KEY environment variable."}

    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY)
        
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=VIDEO_ID,
            order="time",
            textFormat="plainText",
            maxResults=1
        ).execute()

        items = response.get("items", [])
        if not items:
            return {"status": "empty"}

        top_comment = items[0]["snippet"]["topLevelComment"]["snippet"]
        raw_text = top_comment.get("textDisplay", "")
        author = top_comment.get("authorDisplayName", None)
        published_at = top_comment.get("publishedAt", None)

        if contains_unsafe_content(raw_text):
            return {"status": "unsafe", "reason": "content policy"}

        sanitized_text = sanitize_text(raw_text, MAX_CHARS)

        return {
            "status": "ok",
            "comment_text": sanitized_text,
            "author_display": author,
            "published_at": published_at,
            "short_script": {
                "title": "Latest public comment",
                "on_screen_text": sanitized_text,
                "voice_line": "Here is the most recent public comment shared on this video.",
                "caption": "Anonymized public comment from YouTube"
            },
            "notes": None
        }

    except HttpError as e:
        return {"status": "error", "notes": f"YouTube API Error: {e.reason}"}
    except Exception as e:
        return {"status": "error", "notes": str(e)}

if __name__ == "__main__":
    result = get_latest_comment()
    
    # Keep alive için son güncelleme zaman damgası ekleme
    result["last_updated_utc"] = datetime.utcnow().isoformat()
    
    json_output = json.dumps(result, indent=2, ensure_ascii=False)
    
    with open("latest_comment.json", "w", encoding="utf-8") as f:
        f.write(json_output)
        
    print(json_output)
