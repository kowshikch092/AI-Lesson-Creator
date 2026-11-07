import asyncio
from mcp_client1 import youtube_research

async def main():
    try:
        result = await youtube_research(
            "Machine learning fundamentals",
            include_transcripts=True
        )

        print("\nCOMBINED YOUTUBE RESEARCH RESULT")
        print("Query:", result.get("query"))
        print("Video count:", len(result.get("videos", [])))

        for video in result.get("videos", []):
            print("\n-----------------------------")
            print("Title:", video.get("title"))
            print("Channel:", video.get("channel"))

            transcript = video.get("transcript", {})
            print("Transcript type:", type(transcript))
            if isinstance(transcript, dict):
                print("Transcript available:",
                      transcript.get("available"))
                print("Language:", transcript.get("language"))
            else:
                print("Transcript:", transcript)

            print("Transcript type:", type(transcript))

    except Exception as e:
        print("\nTEST FAILED:")
        print(type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())