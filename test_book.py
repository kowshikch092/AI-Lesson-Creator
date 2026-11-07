import asyncio
from mcp_client1 import book_mcp_search

async def main():
    try:
        result = await book_mcp_search("machine learning")
        print("\nBOOK SEARCH RESULT:")
        print(result)
    except Exception as e:
        print("\nBOOK SEARCH FAILED:")
        print(type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())