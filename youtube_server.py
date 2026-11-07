"""Local stdio MCP server exposing YouTube search, metadata and transcript tools."""
import os
from typing import Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from googleapiclient.discovery import build

load_dotenv()
mcp = FastMCP("youtube-research-local")

def youtube_client():
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not configured")
    return build("youtube", "v3", developerKey=key, cache_discovery=False)

@mcp.tool()
def search_youtube_videos(query: str, max_results: int = 5) -> dict:
    """Search YouTube for educational videos and return public metadata."""
    if not query.strip():
        raise ValueError("query cannot be empty")
    response = youtube_client().search().list(part="snippet", q=query, type="video", maxResults=max(1, min(max_results, 10)), relevanceLanguage="en", safeSearch="strict").execute()
    videos = []
    for item in response.get("items", []):
        vid = item["id"]["videoId"]
        sn = item["snippet"]
        videos.append({"video_id": vid, "title": sn.get("title"), "channel": sn.get("channelTitle"), "description": sn.get("description"), "published_at": sn.get("publishedAt"), "url": f"https://www.youtube.com/watch?v={vid}"})
    return {"query": query, "count": len(videos), "videos": videos}

@mcp.tool()
def get_video_transcript(video_id: str, languages: Optional[list[str]] = None) -> dict:
    """Fetch an available transcript; reports unavailable transcripts without inventing text."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        preferred = languages or ["en"]
        selected = None
        for lang in preferred:
            try:
                selected = transcript_list.find_transcript([lang]); break
            except Exception:
                pass
        if selected is None:
            return {"available": False, "video_id": video_id, "reason": "No transcript in requested languages."}
        segments = selected.fetch()
        text = " ".join(getattr(segment, "text", str(segment)) for segment in segments)
        return {"available": True, "video_id": video_id, "language": selected.language_code, "is_generated": selected.is_generated, "text": text[:20000]}
    except Exception as exc:
        return {"available": False, "video_id": video_id, "reason": f"Transcript unavailable: {type(exc).__name__}"}

if __name__ == "__main__":
    mcp.run(transport="stdio")
