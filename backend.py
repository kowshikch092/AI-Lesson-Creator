"""LangGraph backend. Nodes are deliberately separated like the TripMate agents."""
import asyncio
import json
import os
import operator
import uuid
from typing import Annotated, TypedDict, Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from mcp_client1 import (
    tavily_mcp_search,
    book_mcp_search,
    youtube_research,
)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Add it to your .env file.")

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "3000")),
)

class LessonState(TypedDict, total=False):
    topic: str
    audience: str
    supplied_objectives: str
    duration: int
    constraints: str
    include_transcripts: bool
    objective_analysis: str
    web_research: Any
    book_research: Any
    video_research: Any
    research_bundle: dict
    research_summary: str
    lesson_markdown: str
    pedagogy_review: str
    accuracy_review: str
    quality_status: str
    messages: Annotated[list, operator.add]
    errors: Annotated[list[str], operator.add]


def _text(response) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(str(x) for x in content)
    return str(content)

async def objective_agent(state: LessonState):
    prompt = f"""Analyze this lesson request and produce a concise, practical lesson blueprint.
Topic: {state['topic']}
Audience: {state['audience']}
Duration: {state['duration']} minutes
User objectives: {state.get('supplied_objectives') or 'None supplied; propose measurable objectives.'}
Constraints: {state.get('constraints') or 'None'}
Return: (1) 3-5 measurable learning objectives, (2) prerequisite knowledge, (3) key concepts, (4) a minute-by-minute time allocation whose total equals the requested duration, (5) assessment evidence. Do not invent citations."""
    response = await llm.ainvoke([SystemMessage(content="You are an instructional designer. Write measurable, learner-centred objectives."), HumanMessage(content=prompt)])
    return {"objective_analysis": _text(response), "messages": [response]}

async def web_research_agent(state: LessonState):
    try:
        result = await tavily_mcp_search(f"Authoritative, current educational explanations, documentation, examples and common misconceptions about {state['topic']}")
        return {"web_research": result}
    except Exception as exc:
        return {"web_research":None, "errors": [f"Web research unavailable: {type(exc).__name__}: {exc}"]}

async def book_research_agent(state: LessonState):
    try:
        result = await book_mcp_search(state["topic"])
        return {"book_research": str(result)[:5000]}
    except Exception as exc:
        return {"book_research":None,"errors":[ f"Book research unavailable: {type(exc).__name__}: {exc}"]}

async def video_research_agent(state: LessonState):
    try:
        result = await youtube_research(state["topic"], include_transcripts=state.get("include_transcripts", True))
        return {"video_research": str(result)[:5000]}
    except Exception as exc:
        return {"video_research":None, "errors": [f"YouTube research unavailable: {type(exc).__name__}: {exc}"]}
def normalize_research_payload(data):
    """Convert MCP text blocks and JSON strings into Python data."""

    if data is None:
        return None

    if isinstance(data, list):
        parsed = []

        for item in data:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")

                try:
                    parsed.append(json.loads(text))
                except (json.JSONDecodeError, TypeError):
                    parsed.append(text)
            else:
                parsed.append(item)

        if len(parsed) == 1:
            return parsed[0]

        return parsed

    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    return data


def collect_research_sources(provider, data):
    """Extract source records while preserving original evidence."""

    data = normalize_research_payload(data)
    sources = []

    if data is None:
        return sources

    if isinstance(data, dict):
        # Tavily search results
        results = data.get("results")

        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    sources.append({
                        "provider": provider,
                        "title": item.get("title", "Untitled web source"),
                        "url": item.get("url"),
                        "evidence": (
                            item.get("content")
                            or item.get("raw_content")
                            or item.get("snippet")
                            or ""
                        ),
                    })

        # YouTube video results
        videos = data.get("videos")

        if isinstance(videos, list):
            for video in videos:
                if isinstance(video, dict):
                    transcript = normalize_research_payload(
                        video.get("transcript")
                    )

                    transcript_text = ""
                    if isinstance(transcript, dict):
                        transcript_text = transcript.get("text", "")

                    sources.append({
                        "provider": provider,
                        "title": video.get("title", "Untitled video"),
                        "url": video.get("url"),
                        "channel": video.get("channel"),
                        "published_at": video.get("published_at"),
                        "evidence": (
                            transcript_text
                            or video.get("description", "")
                        ),
                        "transcript_available": (
                            transcript.get("available", False)
                            if isinstance(transcript, dict)
                            else False
                        ),
                    })

        # Preserve other structured provider responses
        if not results and not videos:
            sources.append({
                "provider": provider,
                "title": f"{provider} research result",
                "url": None,
                "evidence": json.dumps(data, ensure_ascii=False),
            })

    elif isinstance(data, str):
        # Open Library currently returns formatted text.
        # Preserve the book records without inventing URLs.
        sources.append({
            "provider": provider,
            "title": f"{provider} research results",
            "url": None,
            "evidence": data,
        })

    elif isinstance(data, list):
        for item in data:
            sources.extend(collect_research_sources(provider, item))

    return sources


async def research_aggregator_agent(state: LessonState):
    """Combine, organize and deduplicate the three research providers."""

    providers = {
        "Web": state.get("web_research"),
        "Books": state.get("book_research"),
        "YouTube": state.get("video_research"),
    }

    all_sources = []

    for provider, data in providers.items():
        all_sources.extend(
            collect_research_sources(provider, data)
        )

    # Deduplicate by URL where available, otherwise by title and provider.
    unique_sources = []
    seen = set()

    for source in all_sources:
        url = source.get("url")
        title = source.get("title", "").strip().lower()

        key = (
            url.strip().lower()
            if isinstance(url, str) and url.strip()
            else (source.get("provider"), title)
        )

        if key in seen:
            continue

        seen.add(key)
        unique_sources.append(source)

    research_bundle = {
        "topic": state["topic"],
        "source_count": len(unique_sources),
        "sources": unique_sources,
        "provider_status": {
            provider: (
                "available" if data is not None else "unavailable"
            )
            for provider, data in providers.items()
        },
        "errors": state.get("errors", []),
    }

    research_summary = json.dumps(
        research_bundle,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    return {
        "research_bundle": research_bundle,
        "research_summary": research_summary,
    }
    
async def lesson_generation_agent(state: LessonState):
    """
    Generate a complete lesson using the objective blueprint
    and the consolidated research bundle.
    """

    research_bundle = state.get("research_bundle", {})
    sources = research_bundle.get("sources", [])

    # Give each real source a stable citation label for this lesson.
    formatted_sources = []

    # Keep the generation request below Groq's TPM limit even when a provider
    # returns long transcripts or large search-result excerpts.
    max_sources = 10
    max_evidence_chars = 1200

    for index, source in enumerate(sources[:max_sources], start=1):
        source_id = f"S{index}"
        evidence = source.get("evidence") or source.get("snippet") or ""
        if not isinstance(evidence, str):
            evidence = str(evidence)

        formatted_sources.append({
            "citation_id": source_id,
            "provider": source.get("provider", "Unknown"),
            "title": source.get("title", "Untitled source"),
            "url": source.get("url"),
            "authors": source.get("authors"),
            "publisher": source.get("publisher"),
            "year": source.get("year"),
            "description": source.get("description"),
            "snippet": source.get("snippet"),
            "evidence": evidence[:max_evidence_chars],
        })

    research_context = json.dumps(
        formatted_sources,
        indent=2,
        ensure_ascii=False,
        default=str
    )

    prompt = f"""
Create a complete, teachable lesson in Markdown.

## LESSON DETAILS

Topic: {state['topic']}
Target audience: {state['audience']}
Duration: {state['duration']} minutes

Additional instructions:
{state.get('constraints') or 'None'}

## OBJECTIVE BLUEPRINT

{state.get('objective_analysis', 'No objective analysis available.')}

## CONSOLIDATED RESEARCH SOURCES

{research_context}

## STRICT COMPLETENESS REQUIREMENTS

Your response must contain every section below:

1. Lesson Title
2. Target Audience and Duration
3. Prerequisite Knowledge
4. Learning Objectives
5. Key Concepts
6. Timed Teaching Sequence
7. Detailed Explanations
8. Practical Example
9. Learner Activity
10. Formative Assessment Questions
11. Final Assessment
12. Answer Key
13. Lesson Recap
14. Follow-up Practice
15. References

Do not skip any section.

## STRICT TIMING REQUIREMENT

- The entire lesson must take exactly the requested duration.
- Every activity must have a start and end time.
- No overlapping activities.
- No zero-duration activities.
- The final activity must finish exactly at the requested duration.

For a 45-minute lesson, the timeline must begin at 0
and finish at 45 minutes.

## ASSESSMENT REQUIREMENT

- Include at least 3 formative assessment questions.
- Include at least 3 final assessment questions.
- Provide the correct answer for every question.
- Explain briefly why each answer is correct.

## REFERENCES REQUIREMENT

- Include a References section at the end.
- List only sources supplied in the research bundle.
- Use the supplied citation IDs, such as [S1].
- Never invent a URL or publication detail.
- If no usable source exists, explicitly state that.

## FINAL CHECK

Before returning your response, verify that:
- All 15 sections are present.
- The timeline totals exactly the requested duration.
- Every assessment question has an answer.
- Every citation refers to a supplied source.

Return the complete lesson. Do not stop after the first assessment section.
"""

    response = await llm.ainvoke([
        SystemMessage(
            content=(
                "You are an expert instructional designer and educator. "
                "Create accurate, practical, research-grounded lessons. "
                "Never fabricate sources or citations."
            )
        ),
        HumanMessage(content=prompt)
    ])

    lesson = _text(response)

    return {
        "lesson_markdown": lesson,
        "messages": [response]
    }

async def pedagogy_review_agent(state: LessonState):
    objective_analysis = state.get("objective_analysis", "")
    lesson = state.get("lesson_markdown", "")
    duration = state.get("duration", 45)
    topic = state.get("topic", "")

    prompt = f"""
You are an independent instructional design and learning-quality auditor.

Your task is to evaluate the instructional quality of the lesson.
Do NOT focus on factual accuracy or repeat the work of the factual
accuracy reviewer.

LESSON TOPIC:
{topic}

LEARNING OBJECTIVE ANALYSIS:
{objective_analysis}

PLANNED LESSON DURATION:
{duration} minutes

LESSON CONTENT:
{lesson}

Evaluate the lesson using these criteria:

1. LEARNING OBJECTIVE ALIGNMENT
- Does the lesson directly address the learning objective?
- Do the explanations, examples, activities and assessments support it?
- Identify objectives that are not adequately covered.

2. CLARITY AND STRUCTURE
- Is the lesson logically organized?
- Are explanations understandable for the intended learner?
- Are transitions between concepts clear?
- Identify confusing, repetitive or poorly structured sections.

3. EXPLANATIONS AND EXAMPLES
- Are difficult concepts explained step by step?
- Are examples relevant and understandable?
- Are there enough examples to help learners understand the concepts?
- Identify concepts that need further explanation.

4. PRACTICAL APPLICATION
- Does the lesson connect concepts to real-world situations?
- Are practical activities useful and relevant?
- Can learners apply what they have learned?

5. LEARNER ENGAGEMENT AND ASSESSMENT
- Are activities meaningful and appropriate?
- Do knowledge checks test understanding rather than simple memorization?
- Does the final assessment measure the stated learning objective?
- Are instructions for activities and assessments clear?

6. TIME AND LEARNING FLOW
- Does the lesson realistically fit within {duration} minutes?
- Do the individual time allocations add up correctly?
- Is enough time allocated for explanations, activities and assessments?
- Identify unrealistic or missing time allocations.

7. INSTRUCTIONAL GAPS
- Identify missing prerequisite knowledge.
- Identify missing explanations, examples, activities or assessments.
- Recommend specific improvements.

IMPORTANT RULES:
- Evaluate only the lesson and objective information provided.
- Do not assume a section exists if it is missing.
- Do not give credit for content that is merely mentioned but not explained.
- Give specific examples of weaknesses from the lesson.
- Do not invent learner characteristics or requirements.
- Distinguish major issues from minor suggestions.
- Do not evaluate factual correctness; that belongs to QC Layer 1.

OUTPUT FORMAT:

# QC Layer 2: Instructional Quality Report

## 1. Overall Result
PASS / NEEDS IMPROVEMENT / FAIL

Briefly explain the result.

## 2. Learning Objective Alignment
Identify strengths, weaknesses and missing coverage.

## 3. Clarity and Structure
Identify specific structural or clarity issues.

## 4. Explanations and Examples
Evaluate the depth and usefulness of explanations and examples.

## 5. Practical Application
Evaluate the practical activities and real-world relevance.

## 6. Learner Engagement and Assessment
Evaluate activities, knowledge checks and final assessment.

## 7. Time and Learning Flow
Check whether the lesson fits the planned duration.

## 8. Instructional Gaps
List missing or insufficient instructional elements.

## 9. Recommended Improvements
Provide numbered, actionable recommendations.

## 10. Final QC Decision
PASS / NEEDS IMPROVEMENT / FAIL

Explain what must be improved before approval.

Decision guidance:
- PASS: The lesson is instructionally effective and aligned with the objective.
- NEEDS IMPROVEMENT: The lesson is usable but has notable instructional weaknesses.
- FAIL: Major gaps prevent the lesson from effectively achieving its objective.
"""

    response = await llm.ainvoke([
        SystemMessage(
            content="You are a rigorous, independent instructional quality auditor."
        ),
        HumanMessage(content=prompt)
    ])

    return {"pedagogy_review": _text(response)}

async def accuracy_review_agent(state: LessonState):
    

    research_bundle = state.get("research_bundle", {})
    sources = research_bundle.get("sources", [])

    # Keep compact source evidence for QC
    compact_sources = []

    for i, source in enumerate(sources[:12], start=1):
        compact_sources.append({
            "id": f"S{i}",
            "provider": source.get("provider", ""),
            "title": source.get("title", ""),
            "url": source.get("url", ""),
            "snippet": source.get("snippet", "")[:350]
        })

    research_context = json.dumps(
    compact_sources,
    ensure_ascii=False
    )

    lesson = state.get("lesson_markdown", "")

    # Limit lesson content sent to the reviewer
    lesson = lesson[:10000]

    prompt = f"""
Audit the factual accuracy of this lesson.

RESEARCH EVIDENCE:
{research_context}

LESSON:
{lesson}

Check:
1. Factual correctness.
2. Unsupported or misleading claims.
3. Source reliability and relevance.
4. Citation integrity.
5. Content gaps and inconsistencies.

Do not claim that a source supports a statement unless
its supplied evidence actually supports that statement.

Produce a structured QC Layer 1 report with:
- Overall Result
- Factual Accuracy Findings
- Unsupported or Misleading Claims
- Source Reliability and Relevance
- Citation Integrity
- Content Gaps and Inconsistencies
- Recommended Improvements
- Final QC Decision

Final QC Decision must be PASS, NEEDS IMPROVEMENT, or FAIL.
"""
    response = await llm.ainvoke([
        SystemMessage(
            content=(
                "You are an independent factual accuracy auditor "
                "and research evidence reviewer. Your responsibility "
                "is to identify errors, unsupported claims and "
                "source-quality problems. Never fabricate verification."
            )
        ),
        HumanMessage(content=prompt)
    ])

    return {
        "accuracy_review": _text(response)
    }

async def quality_merge_agent(state: LessonState):

    accuracy_report = state.get("accuracy_review", "")
    pedagogy_report = state.get("pedagogy_review", "")

    def get_decision(report):
        import re

        match = re.search(
            r"##\s*10\.\s*Final QC Decision\s*\n+\s*\**"
            r"(PASS|NEEDS IMPROVEMENT|FAIL)\**",
            report,
            re.IGNORECASE
        )

        if not match:
            return "NEEDS IMPROVEMENT"

        return match.group(1).upper()

    accuracy_decision = get_decision(accuracy_report)
    pedagogy_decision = get_decision(pedagogy_report)

    if "FAIL" in [accuracy_decision, pedagogy_decision]:
        overall = "FAIL"
    elif "NEEDS IMPROVEMENT" in [
        accuracy_decision,
        pedagogy_decision
    ]:
        overall = "NEEDS REVISION"
    else:
        overall = "READY"

    return {
        "quality_status": f"""
        Overall QC Status: {overall}

        QC Layer 1 — Factual Accuracy: {accuracy_decision}

        QC Layer 2 — Instructional Quality: {pedagogy_decision}

        Both independent QC reports have been generated.
        """
    }
def build_lesson_graph(checkpointer=None):
    graph = StateGraph(LessonState)
    graph.add_node("objective_agent", objective_agent)
    graph.add_node("web_research_agent", web_research_agent)
    graph.add_node("book_research_agent", book_research_agent)
    graph.add_node("video_research_agent", video_research_agent)
    graph.add_node("research_aggregator_agent", research_aggregator_agent)
    graph.add_node("lesson_generation_agent", lesson_generation_agent)
    graph.add_node("pedagogy_review_agent", pedagogy_review_agent)
    graph.add_node("accuracy_review_agent", accuracy_review_agent)
    graph.add_node("quality_merge_agent", quality_merge_agent)

    graph.add_edge(START, "objective_agent")
    graph.add_edge("objective_agent", "web_research_agent")
    graph.add_edge("objective_agent", "book_research_agent")
    graph.add_edge("objective_agent", "video_research_agent")
    # Explicit fan-in edges make each downstream node wait for every parallel branch.
    graph.add_edge(["web_research_agent", "book_research_agent", "video_research_agent"], "research_aggregator_agent")
    graph.add_edge("research_aggregator_agent", "lesson_generation_agent")
    graph.add_edge("lesson_generation_agent", "accuracy_review_agent")
    graph.add_edge("accuracy_review_agent", "pedagogy_review_agent")
    graph.add_edge("pedagogy_review_agent", "quality_merge_agent")
    graph.add_edge("quality_merge_agent", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())

async def run_lesson_workflow(topic: str, audience: str, objectives: str = "", duration: int = 45,
                              constraints: str = "", include_transcripts: bool = True,
                              thread_id: str | None = None):
    """Run one lesson graph invocation; PostgreSQL is used when DATABASE_URL exists."""
    thread_id = thread_id or f"lesson_{uuid.uuid4().hex}"
    initial_state = {
        "topic": topic, "audience": audience, "supplied_objectives": objectives,
        "duration": duration, "constraints": constraints,
        "include_transcripts": include_transcripts, "messages": [], "errors": [],
    }
    config = {"configurable": {"thread_id": thread_id}}
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            if "sslmode=" not in database_url:
                database_url += ("&" if "?" in database_url else "?") + "sslmode=require"
        except Exception as exc:
            raise RuntimeError(f"PostgreSQL checkpointer initialization failed: {exc}") from exc
        async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
            await checkpointer.setup()
            workflow = build_lesson_graph(checkpointer)
            result = await workflow.ainvoke(initial_state, config=config)
    else:
        workflow = build_lesson_graph(MemorySaver())
        result = await workflow.ainvoke(initial_state, config=config)
    result["thread_id"] = thread_id
    return result
