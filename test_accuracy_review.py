# import asyncio

# from backend import accuracy_review_agent


# async def main():

#     test_state = {
#         "topic": "Machine Learning Fundamentals",

#         "objective_analysis": """
#         Students should be able to:
#         1. Define machine learning.
#         2. Explain supervised learning.
#         3. Explain unsupervised learning.
#         """,

#         "research_bundle": {
#             "sources": [
#                 {
#                     "provider": "Web",
#                     "title": "Introduction to Machine Learning",
#                     "url": "https://developers.google.com/machine-learning/intro",
#                     "snippet": (
#                         "An introduction to machine learning "
#                         "concepts and terminology."
#                     )
#                 },
#                 {
#                     "provider": "Books",
#                     "title": "Hands-On Machine Learning",
#                     "authors": "Aurélien Géron",
#                     "publisher": "O'Reilly Media",
#                     "year": 2019
#                 }
#             ]
#         },

#         "lesson_markdown": """
#         # Machine Learning Fundamentals

#         ## Learning Objectives

#         1. Define machine learning.
#         2. Explain supervised learning.
#         3. Explain unsupervised learning.

#         ## Explanation

#         Machine learning allows systems to learn patterns
#         from data.

#         Supervised learning uses labelled training data.

#         Unsupervised learning uses unlabelled data.

#         ## Practical Example

#         A spam detection system can use supervised
#         machine learning to classify emails.
#         """
#     }

#     print("Running QC Layer 1...")

#     result = await accuracy_review_agent(test_state)

#     report = result["accuracy_review"]
#     report_lower = report.lower()

#     assert "100" in report_lower, (
#         "QC failed to identify the false accuracy claim."
#     )

#     assert "s99" in report_lower, (
#         "QC failed to identify the invalid citation."
#     )

#     assert any(
#         word in report_lower
#         for word in ["unsupported", "unverified", "not verifiable"]
#     ), "QC failed to identify unsupported claims."

#     print("\nCRITICAL QC CHECKS PASSED")

#     print("\n========== ACCURACY QC REPORT ==========\n")
#     print(report)

#     assert isinstance(report, str)
#     assert len(report) > 300

#     assert "Factual Accuracy" in report
#     assert "Final QC Decision" in report or "QC Decision" in report

#     print("\nACCURACY QC TEST PASSED")


# if __name__ == "__main__":
#     asyncio.run(main())





## Running QC Layer 2...


import asyncio
from backend import pedagogy_review_agent


async def main():
    print("Running QC Layer 2...")

    test_state = {
        "topic": "Machine Learning Fundamentals",
        "duration": 45,

        "objective_analysis": """
        Learning Objective:
        Explain machine learning and distinguish between
        supervised and unsupervised learning.

        Expected learner outcome:
        Learners should be able to explain both approaches
        and identify examples of each.
        """,

        "lesson_markdown": """
        # Machine Learning Fundamentals

        ## Introduction (5 minutes)
        Machine learning is a field of artificial intelligence.

        ## Supervised Learning (5 minutes)
        Supervised learning uses labelled training data.

        ## Unsupervised Learning (5 minutes)
        Unsupervised learning uses unlabelled data.

        ## Example (5 minutes)
        An email spam filter can use machine learning.

        ## Activity (5 minutes)
        Think about one application of machine learning.

        ## Assessment (5 minutes)
        1. What is machine learning?
        2. What is supervised learning?

        ## Conclusion
        Machine learning helps computers learn from data.
        """
    }

    result = await pedagogy_review_agent(test_state)

    report = result["pedagogy_review"]

    assert isinstance(report, str)
    assert len(report) > 300

    report_lower = report.lower()

    required_checks = [
        "learning objective",
        "clarity",
        "example",
        "assessment",
        "time",
        "final qc decision"
    ]

    for check in required_checks:
        assert check in report_lower, (
            f"QC report is missing expected section: {check}"
        )

    print("\n========== INSTRUCTIONAL QUALITY REPORT ==========\n")
    print(report)

    print("\nINSTRUCTIONAL QUALITY QC TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())