import asyncio

from backend import lesson_generation_agent


async def main():

    test_state = {
        "topic": "Machine Learning Fundamentals",
        "audience": "Final-year undergraduate computer science students",
        "duration": 45,
        "constraints": (
            "Include a simple practical example. "
            "Keep the lesson suitable for beginners."
        ),

        "objective_analysis": """
        Learning objectives:
        1. Define machine learning.
        2. Distinguish supervised and unsupervised learning.
        3. Explain the basic machine learning workflow.
        4. Identify one real-world application.
        """,

        "research_bundle": {
            "sources": [
                {
                    "provider": "Web",
                    "title": "Introduction to Machine Learning",
                    "url": "https://developers.google.com/machine-learning/intro",
                    "snippet": (
                        "An introduction to machine learning concepts "
                        "and common terminology."
                    )
                },
                {
                    "provider": "Books",
                    "title": "Hands-On Machine Learning",
                    "authors": "Aurélien Géron",
                    "publisher": "O'Reilly Media",
                    "year": 2019,
                    "url": None
                },
                {
                    "provider": "YouTube",
                    "title": "Machine Learning Explained",
                    "url": "https://www.youtube.com/watch?v=EuBBz3bI-aA",
                    "transcript": (
                        "Example transcript content for testing."
                    )
                }
            ]
        }
    }

    print("Generating lesson...")

    result = await lesson_generation_agent(test_state)

    lesson = result["lesson_markdown"]
    
    required_sections = [
    "Learning Objectives",
    "Prerequisite",
    "Timed Teaching Sequence",
    "Detailed Explanations",
    "Practical Example",
    "Learner Activity",
    "Formative Assessment",
    "Final Assessment",
    "Answer Key",
    "Recap",
    "Follow-up Practice",
    "References"
]

    missing_sections = [
        section for section in required_sections
        if section.lower() not in lesson.lower()
    ]

    print("\n========== SECTION CHECK ==========")

    for section in required_sections:
        status = (
            "MISSING"
            if section in missing_sections
            else "PASS"
        )
        print(f"{section}: {status}")

    if missing_sections:
        raise AssertionError(
            f"Lesson incomplete. Missing: {missing_sections}"
        )

    print("\nLESSON GENERATOR TEST PASSED")
    print("\nLesson character count:", len(lesson))
    print("Lesson word count:", len(lesson.split()))
        
    print("\n========== GENERATED LESSON ==========\n")
    print(lesson)

    # Basic output checks
    assert isinstance(lesson, str)
    assert len(lesson) > 500
    assert "Machine Learning" in lesson or "machine learning" in lesson.lower()

    print("\nLESSON GENERATOR TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())