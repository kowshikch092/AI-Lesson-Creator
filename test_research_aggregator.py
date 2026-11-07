import asyncio

from mcp_client1 import (
    tavily_research,
    book_research,
    youtube_research,
)

from backend import research_aggregator_agent


async def main():
    topic = "Machine learning fundamentals"

    print("Collecting research from three providers...")

    web, books, videos = await asyncio.gather(
        tavily_research(topic),
        book_research(topic),
        youtube_research(topic, include_transcripts=True),
        return_exceptions=True,
    )

    state = {
        "topic": topic,
        "web_research": None if isinstance(web, Exception) else web,
        "book_research": None if isinstance(books, Exception) else books,
        "video_research": None if isinstance(videos, Exception) else videos,
        "errors": [
            f"Research error: {result}"
            for result in (web, books, videos)
            if isinstance(result, Exception)
        ],
    }

    result = await research_aggregator_agent(state)

    bundle = result["research_bundle"]

    print("\nRESEARCH AGGREGATION RESULT")
    print("Topic:", bundle["topic"])
    print("Total sources:", bundle["source_count"])
    print("Provider status:", bundle["provider_status"])

    print("\nSOURCES:")
    for source in bundle["sources"]:
        print("\nProvider:", source["provider"])
        print("Title:", source["title"])
        print("URL:", source.get("url"))

    print("\nErrors:", bundle["errors"])

    assert bundle["topic"] == topic
    assert isinstance(bundle["sources"], list)
    assert bundle["source_count"] == len(bundle["sources"])

    print("\nRESEARCH AGGREGATOR TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())