import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq


# Environment configuration
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

PROJECT_DIR = Path(__file__).resolve().parent
YOUTUBE_SERVER_PATH = PROJECT_DIR / "youtube_server.py"
YOUTUBE_ENV = os.environ.copy()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY
)
client=MultiServerMCPClient(
    {
        "tavily":{
            "transport":"http",
            "url": (
                "https://mcp.tavily.com/mcp/?"
                + urlencode({"tavilyApiKey": TAVILY_API_KEY})
            ),
        },
        "Book_Research":{
            "transport": "http",
            "url": "https://openlibrary.caseyjhand.com/mcp",
        },
        "YouTube_Research":{
            "transport": "stdio",
            "command":sys.executable,
            "args":[str(YOUTUBE_SERVER_PATH)],
            "env":YOUTUBE_ENV
        },
    }
)

async def get_all_tools():
    all_tools=[]
    
    for server_name in("tavily","Book_Research","YouTube_Research"):
        try:
            tools = await client.get_tools(server_name = server_name)
            all_tools.extend(tools)
            print(
                f"\nAvailable tools from "
                f"{server_name} MCP:\n"
            )
            
            for tool in tools:
                print(tool.name)
        except Exception as e:
            print(f"\nCould not connect to {server_name} MCP:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {e}")
# Tavily MCP tool

search_tool = None
async def initialize_mcp():
    global search_tool
    if search_tool is not None:
        return
    tools = await client.get_tools(server_name="tavily")
    tools_by_name = {
        tool.name: tool
        for tool in tools
    }
    search_tool = tools_by_name.get("tavily_search")
    
    if search_tool is None:
        available_tool = ", ".join(tools_by_name.keys())
        raise RuntimeError(
            "Tavily MCP connected, but the"
            "tavily_search tool was not found. "
            f"Available tools: {available_tool or None}"
        )

async def tavily_mcp_search(query: str):
    await initialize_mcp()
    result = await search_tool.ainvoke(
        {
            "query": query
        }
    )
    return result

# Book Research MCP tools

book_search_tool = None

async def initialize_book_tools():
    global book_search_tool
    if book_search_tool is not None:
        return
    tools = await client.get_tools(server_name="Book_Research")
    tools_by_name = {
        tool.name: tool
        for tool in tools
    }
    book_search_tool = tools_by_name.get("openlibrary_search_books")
    if book_search_tool is None:
        available_tool = ", ".join(tools_by_name.keys())
        raise RuntimeError(
            "Book Research MCP connected, but the"
            "openlibrary_search_books tool was not found"
            f"Available tools: {available_tool or None}"
        )

async def book_mcp_search(query: str):
    await initialize_book_tools()
    result = await book_search_tool.ainvoke(
        {
            "query": query
        }
    )
    return result

# YouTube MCP tools

youtube_search_tool = None
youtube_transcript_tool = None


def normalize_mcp_result(result):
    """Convert MCP responses into normal Python data."""

    if isinstance(result, list):
        parsed_blocks = []

        for item in result:
            if isinstance(item, dict):
                text_content = item.get("text")
                content_type = item.get("type")
            else:
                text_content = getattr(item, "text", None)
                content_type = getattr(item, "type", None)

            if content_type == "text" and isinstance(text_content, str):
                try:
                    parsed_blocks.append(json.loads(text_content))
                except json.JSONDecodeError:
                    parsed_blocks.append(text_content)
            else:
                parsed_blocks.append(item)

        if len(parsed_blocks) == 1:
            return parsed_blocks[0]

        return parsed_blocks

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result

    return result


async def initialize_youtube_tools():
    global youtube_search_tool, youtube_transcript_tool

    if youtube_search_tool is not None:
        return

    tools = await client.get_tools(server_name="YouTube_Research")

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    youtube_search_tool = tools_by_name.get("search_youtube_videos")
    youtube_transcript_tool = tools_by_name.get("get_video_transcript")

    if youtube_search_tool is None:
        raise RuntimeError(
            "YouTube MCP connected, but search_youtube_videos was not found. "
            f"Available tools: {', '.join(tools_by_name.keys())}"
        )


async def youtube_mcp_search(query: str, max_results: int = 5):
    await initialize_youtube_tools()

    result = await youtube_search_tool.ainvoke({
        "query": query,
        "max_results": max_results
    })
    normalized = normalize_mcp_result(result)
    print("Normalized YouTube response type:", type(normalized))
    return normalized


async def youtube_mcp_transcript(video_id: str):
    await initialize_youtube_tools()

    if youtube_transcript_tool is None:
        raise RuntimeError("get_video_transcript tool is unavailable")

    result = await youtube_transcript_tool.ainvoke({
        "video_id": video_id
    })
    normalized = normalize_mcp_result(result)
    print("Normalized transcript response type:", type(normalized))
    return normalized


async def tavily_research(query: str):
    """Compatibility name used by the lesson workflow."""
    return await tavily_mcp_search(query)


async def book_research(query: str):
    """Compatibility name used by the lesson workflow."""
    return await book_mcp_search(query)


async def youtube_research(query: str, include_transcripts: bool = True):
    """Search for videos and optionally attach available transcripts."""
    result = await youtube_mcp_search(query)
    if not include_transcripts or not isinstance(result, dict):
        return result

    videos = result.get("videos")
    if not isinstance(videos, list):
        return result

    enriched_videos = []
    for video in videos:
        if not isinstance(video, dict):
            enriched_videos.append(video)
            continue
        enriched_video = dict(video)
        video_id = video.get("video_id")
        if video_id:
            enriched_video["transcript"] = await youtube_mcp_transcript(video_id)
        enriched_videos.append(enriched_video)
    return {**result, "videos": enriched_videos}