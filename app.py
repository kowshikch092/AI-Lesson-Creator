import asyncio
import ast
import json
import re
import uuid
from io import BytesIO
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
)

import streamlit as st
from backend import run_lesson_workflow


def create_pdf(title, markdown_content):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocumentTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#183153"),
        spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#24527A"),
        spaceBefore=14,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SubHeading",
        parent=styles["Heading3"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#34495E"),
        spaceBefore=10,
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="SmallCustom",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
    ))

    story = [Paragraph(escape(title), styles["DocumentTitle"])]

    def inline_format(text):
        text = escape(text.strip())
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
        return re.sub(
            r"\[(.*?)\]\((https?://.*?)\)",
            r"<link href='\2' color='blue'>\1</link>",
            text,
        )

    lines = str(markdown_content).splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            story.append(Spacer(1, 4))
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", line):
            story.append(HRFlowable(
                width="100%",
                thickness=0.7,
                color=colors.lightgrey,
                spaceBefore=5,
                spaceAfter=10,
            ))
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r"^\|?[\s|:-]+\|?$", next_line):
                table_data = [[
                    Paragraph(inline_format(cell), styles["SmallCustom"])
                    for cell in line.strip("|").split("|")
                ]]
                i += 2
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_data.append([
                        Paragraph(inline_format(cell), styles["SmallCustom"])
                        for cell in lines[i].strip().strip("|").split("|")
                    ])
                    i += 1

                table = Table(table_data, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#183153")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.extend([table, Spacer(1, 10)])
                continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            style = (
                styles["Heading1"]
                if level == 1
                else styles["SectionHeading"]
                if level == 2
                else styles["SubHeading"]
            )
            story.append(Paragraph(
                inline_format(heading_match.group(2)),
                style,
            ))
            i += 1
            continue

        if re.match(r"^[-*]\s+", line):
            story.append(Paragraph(
                "• " + inline_format(re.sub(r"^[-*]\s+", "", line)),
                styles["BodyCustom"],
            ))
            i += 1
            continue

        story.append(Paragraph(inline_format(line), styles["BodyCustom"]))
        i += 1

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20 * mm, 12 * mm, "AI Lesson Creator")
        canvas.drawRightString(
            A4[0] - 20 * mm,
            12 * mm,
            f"Page {document.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer.getvalue()


def build_structured_references(result):
    sections = []

    web_data = result.get("web_research", [])

    if isinstance(web_data, str):
        try:
            web_data = ast.literal_eval(web_data)
        except (ValueError, SyntaxError):
            web_data = []

    if isinstance(web_data, list):
        for item in web_data:
            if isinstance(item, dict) and item.get("text"):
                try:
                    parsed = json.loads(item["text"])
                    if isinstance(parsed, dict):
                        web_data = parsed
                        break
                except (ValueError, TypeError):
                    pass

    web_results = web_data.get("results", []) if isinstance(web_data, dict) else []
    sections.append("# 1. Web Research References\n")

    if web_results:
        for i, source in enumerate(web_results, 1):
            sections.append(f"## W{i}. {source.get('title', 'Untitled source')}\n")
            sections.append(
                f"- **Website:** "
                f"{urlparse(source.get('url', '')).netloc or 'Not provided'}"
            )
            sections.append(f"- **URL:** {source.get('url', 'Not available')}")
            sections.append(
                f"- **Description:** {source.get('content', 'Not available')}"
            )
            sections.append(
                f"- **Search relevance score:** "
                f"{source.get('score', 'Not available')}"
            )
            sections.append("")
    else:
        sections.append("No structured web references were available.\n")

    book_data = result.get("book_research", "")

    if isinstance(book_data, list):
        book_text = "\n".join(
            str(item.get("text", item)) if isinstance(item, dict)
            else str(item)
            for item in book_data
        )
    elif isinstance(book_data, dict):
        book_text = json.dumps(book_data, ensure_ascii=False)
    else:
        book_text = str(book_data)

    book_text = book_text.replace("\\n", "\n").replace("\\t", " ")
    sections.append("# 2. Book References\n")
    book_entries = re.split(r"(?m)^##\s+", book_text)
    book_count = 0

    for entry in book_entries:
        lines = [line.strip() for line in entry.splitlines() if line.strip()]
        if not lines:
            continue

        title = lines[0].strip("* ")
        if title.lower().startswith("total results"):
            continue

        def extract_field(pattern):
            match = re.search(pattern, entry, re.IGNORECASE)
            return match.group(1).strip("* ") if match else "Not available"

        if not re.search(r"Work ID:", entry):
            continue

        book_count += 1
        work_id = extract_field(r"Work ID:\*\*\s*([^\s]+)")
        sections.append(f"## B{book_count}. {title}\n")
        sections.append(
            f"- **Author:** "
            f"{extract_field(r'Authors:\*\*\s*([^\n]+)')}"
        )
        sections.append(
            f"- **Publisher:** "
            f"{extract_field(r'publishers:\*\*\s*([^\n]+)')}"
        )
        sections.append(
            f"- **First published:** "
            f"{extract_field(r'First published:\s*(\d+)')}"
        )
        sections.append(f"- **Open Library Work ID:** {work_id}")
        sections.append(
            f"- **Edition ID:** "
            f"{extract_field(r'Selected edition ID:\*\*\s*([^\s]+)')}"
        )
        sections.append(
            f"- **Language:** "
            f"{extract_field(r'languages:\*\*\s*([^\n]+)')}"
        )
        sections.append(
            f"- **Open Library link:** "
            f"https://openlibrary.org/works/{work_id}"
        )
        sections.append("")

    if book_count == 0:
        sections.append("No structured book references were available.\n")

    video_data = result.get("video_research", {})

    if isinstance(video_data, str):
        try:
            video_data = ast.literal_eval(video_data)
        except (ValueError, SyntaxError):
            video_data = {}

    sections.append("# 3. YouTube Video References\n")
    videos = video_data.get("videos", []) if isinstance(video_data, dict) else []

    if videos:
        for i, video in enumerate(videos, 1):
            transcript = video.get("transcript", {})
            available = (
                transcript.get("available", False)
                if isinstance(transcript, dict)
                else False
            )
            sections.append(f"## V{i}. {video.get('title', 'Untitled video')}\n")
            sections.append(f"- **Channel:** {video.get('channel', 'Not available')}")
            sections.append(
                f"- **Published:** {video.get('published_at', 'Not available')}"
            )
            sections.append(
                f"- **Video ID:** {video.get('video_id', 'Not available')}"
            )
            sections.append(f"- **Video URL:** {video.get('url', 'Not available')}")
            sections.append(
                f"- **Transcript available:** "
                f"{'Yes' if available else 'No'}"
            )
            sections.append("")
    else:
        sections.append("No structured YouTube references were available.\n")

    return "\n".join(sections)


st.set_page_config(page_title="AI Lesson Creator", page_icon="📚", layout="wide")
st.title("📚 AI Lesson Creator")
st.caption("Research-backed lesson planning with LangGraph, Groq and three MCP servers.")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"lesson_{uuid.uuid4().hex}"
if "lesson_result" not in st.session_state:
    st.session_state.lesson_result = None
if "lesson_draft" not in st.session_state:
    st.session_state.lesson_draft = ""
if "lesson_approved" not in st.session_state:
    st.session_state.lesson_approved = False
with st.sidebar:
    st.subheader("Lesson settings")
    duration = st.number_input("Lesson duration (minutes)", min_value=10, max_value=180, value=45, step=5)
    learner_level = st.selectbox("Learner level", ["Beginner", "Intermediate", "Advanced"])
    include_transcripts = st.checkbox("Try to retrieve YouTube transcripts", value=True)
    st.caption("Transcript availability depends on each video's settings and YouTube access.")

with st.form("lesson_request"):
    topic = st.text_input("Lesson topic", placeholder="e.g. HTTP Requests and Responses")
    audience = st.text_input("Target learners", placeholder="e.g. First-year computer science students")
    objectives = st.text_area("Learning objectives (optional)", placeholder="Enter your objectives, one per line. The AI can also propose them.", height=110)
    constraints = st.text_area("Additional instructions (optional)", placeholder="e.g. Include a hands-on Python activity and a short quiz.", height=80)
    submitted = st.form_submit_button("Create lesson", type="primary", use_container_width=True)

if submitted:
    if not topic.strip():
        st.error("Please enter a lesson topic.")
    else:
        with st.spinner("Researching sources and creating your lesson..."):
            try:
                result = asyncio.run(run_lesson_workflow(
                    topic=topic.strip(),
                    audience=audience.strip() or learner_level,
                    objectives=objectives.strip(),
                    duration=int(duration),
                    constraints=constraints.strip(),
                    include_transcripts=include_transcripts,
                    thread_id=st.session_state.thread_id,
                ))
                st.session_state.lesson_result = result
                st.session_state.lesson_draft = result.get("lesson_markdown", "")
                st.session_state.lesson_approved = False
            except Exception as exc:
                st.exception(exc)

result = st.session_state.lesson_result
if result:
    st.divider()

    st.subheader("Instructor Review and Editing")

    st.text_area(
        "Edit your lesson below",
        key="lesson_draft",
        height=600,
    )

    if st.button("Save lesson edits", type="primary"):
        st.success("Lesson edits saved successfully!")

    st.markdown("### Lesson Preview")
    st.markdown(st.session_state.lesson_draft)
    st.divider()
    st.subheader("Instructor Approval")

    if st.button("Approve Final Lesson", type="primary"):
        if st.session_state.lesson_draft.strip():
            st.session_state.lesson_approved = True
            st.success("Lesson approved successfully!")
        else:
            st.error("Cannot approve an empty lesson.")

    if st.session_state.lesson_approved:
        st.success("Status: APPROVED")
    else:
        st.warning("Status: PENDING APPROVAL")

    with st.expander("Learning objectives and analysis"):
        st.markdown(result.get("objective_analysis", "Not available."))
    with st.expander("Research sources"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Web research — Tavily**")
            st.write(result.get("web_research", "No results"))
        with col2:
            st.markdown("**Book research — Open Library**")
            st.write(result.get("book_research", "No results"))
        with col3:
            st.markdown("**Video research — YouTube**")
            st.write(result.get("video_research", "No results"))
    with st.expander("Quality review"):
        st.markdown("**Pedagogical review**")
        st.write(result.get("pedagogy_review", "Not available"))
        st.markdown("**Accuracy and evidence review**")
        st.write(result.get("accuracy_review", "Not available"))
        st.markdown("**Final quality status**")
        st.write(result.get("quality_status", "Not available"))

    # --------------------------------
    # PDF EXPORT SECTION
    # --------------------------------

    st.divider()
    st.subheader("Export Final Lesson and QC Reports")

    if st.session_state.lesson_approved:

        st.success("Your lesson is approved and ready for PDF export.")

        lesson_pdf = create_pdf(
            "Final Approved Lesson",
            st.session_state.lesson_draft,
        )
        accuracy_pdf = create_pdf(
            "QC Layer 1 - Factual Accuracy Report",
            str(result.get("accuracy_review", "Report unavailable")),
        )
        pedagogy_pdf = create_pdf(
            "QC Layer 2 - Instructional Quality Report",
            str(result.get("pedagogy_review", "Report unavailable")),
        )

        references = build_structured_references(result)
        references_pdf = create_pdf(
            "Research References and Bibliography",
            references,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📘 Download Final Lesson (PDF)",
                data=lesson_pdf,
                file_name="final_lesson.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.download_button(
                "📄 Download Accuracy Report (PDF)",
                data=accuracy_pdf,
                file_name="accuracy_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "📄 Download Instructional Report (PDF)",
                data=pedagogy_pdf,
                file_name="instructional_quality_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            st.download_button(
                "📚 Download Research References (PDF)",
                data=references_pdf,
                file_name="research_references.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    else:
        st.warning("Please approve the lesson before exporting PDFs.")

    if st.button("Start a new lesson"):
        st.session_state.thread_id = f"lesson_{uuid.uuid4().hex}"
        st.session_state.lesson_result = None
        st.session_state.lesson_draft = ""
        st.session_state.lesson_approved = False
        st.rerun()
