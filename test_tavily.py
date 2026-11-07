import asyncio
from mcp_client1 import tavily_mcp_search

async def main():
    try:
        result = await tavily_mcp_search(
            "Machine learning fundamentals and applications"
        )

        print("\nTAVILY SEARCH RESULT:")
        print(result)

    except Exception as e:
        print("\nTAVILY SEARCH FAILED:")
        print(type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())