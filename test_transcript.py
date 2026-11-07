import asyncio
from mcp_client1 import youtube_mcp_transcript

async def main():
    video_id = "EuBBz3bI-aA"

    try:
        result = await youtube_mcp_transcript(video_id)

        print("\nYOUTUBE TRANSCRIPT RESULT:")
        print(result)

    except Exception as e:
        print("\nTRANSCRIPT TEST FAILED:")
        print(type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())