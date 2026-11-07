# import asyncio
# from mcp_client1 import youtube_mcp_search

# async def main():
#     try:
#         result = await youtube_mcp_search(
#             "Machine learning fundamentals",
#             max_results=5
#         )

#         print("\nYOUTUBE SEARCH RESULT:")
#         print(result)

#     except Exception as e:
#         print("\nYOUTUBE SEARCH FAILED:")
#         print(type(e).__name__, e)

# if __name__ == "__main__":
#     asyncio.run(main())



import asyncio
from backend import run_lesson_workflow


async def main():

    print("Running complete lesson workflow with both QC layers...")

    result = await run_lesson_workflow(
        topic="Machine Learning Fundamentals",
        audience="Beginner computer science students",
        objectives=(
            "Explain machine learning and distinguish "
            "between supervised and unsupervised learning."
        ),
        duration=45,
        include_transcripts=False
    )

    accuracy = result.get("accuracy_review", "")
    pedagogy = result.get("pedagogy_review", "")
    status = result.get("quality_status", "")
    lesson = result.get("lesson_markdown", "")

    assert lesson, "Lesson generation failed."
    assert accuracy, "QC Layer 1 report missing."
    assert pedagogy, "QC Layer 2 report missing."
    assert status, "Combined QC status missing."

    assert "Factual Accuracy" in accuracy
    assert "Instructional Quality" in pedagogy

    print("\n========== INTEGRATION RESULTS ==========")

    print("\nLesson generated:", bool(lesson))
    print("QC Layer 1 generated:", bool(accuracy))
    print("QC Layer 2 generated:", bool(pedagogy))

    print("\n========== FINAL QC STATUS ==========")
    print(status)

    print("\nQC INTEGRATION TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())