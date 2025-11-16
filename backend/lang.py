from typing import List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.units import mm
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import os, re
from datetime import datetime
import numpy as np
from random import choice
from langchain_community.utilities import WikipediaAPIWrapper
from io import BytesIO
import base64
from dotenv import load_dotenv
import re

load_dotenv ()

groq_api_key = os.getenv("GROQ_API_KEY")
wiki_wrapper = WikipediaAPIWrapper()

# ==========================
# --- Graph State ---
# ==========================
class GraphState(TypedDict):
    topic: str
    heading: str
    intro: str
    subtopics: List[str]
    content: Dict[str, str]
    summaries: Dict[str, str]
    insights: Dict[str, str]
    conclusion: str
 
    pdf_path: str
    pdf_base64: str
    language: str
    pages: int
    

# ==========================
# --- Initialize LLM ---
# ==========================
groq_llm = ChatGroq(
    api_key=groq_api_key,  # Replace with your key
    temperature=0.7,
    model_name="llama-3.1-8b-instant"
)

# ==========================
# --- Agents ---
# ==========================
def intro_agent(state: GraphState) -> Dict[str, Any]:
    """Generate a short 4-5 line introduction about the main topic."""
    prompt = f"Write a concise introduction (about 100-120 words) about the topic '{state['topic']}'."
    response = groq_llm.invoke(prompt)
    return {"intro": getattr(response, "content", str(response))}

def planner_agent(state: GraphState) -> Dict[str, Any]:
    topic = state["topic"]
    pages = state.get("pages", 3)
    
    # Dynamic structure:
    # Page 1: Introduction + Subtopic 1 (1 subtopic)
    # Pages 2 to (pages-1): 2 subtopics per page (2 * (pages-2) subtopics)
    # Last Page: Conclusion (0 subtopics)
    # For pages=3: 1 + 2*1 + 0 = 3 subtopics
    # For pages=5: 1 + 2*3 + 0 = 7 subtopics
    # For pages=7: 1 + 2*5 + 0 = 11 subtopics
    num_subtopics = 1 + (2 * (pages - 2))
    
    print(f"📊 Pages: {pages}")
    print(f"📊 Subtopics needed: {num_subtopics} (Intro page: 1 subtopic + Middle pages: 2 per page + Conclusion page)")
    
    prompt1 = f"Give a 2-3 word heading title for the topic '{topic}' If the topic is already of 1-4 words with correct english just give same title with corrected english if topic is large than 4 words summarize it to 4 words ."
    prompt = f"Break the topic '{topic}' into {num_subtopics} major subtopics. Return only bullet points."
    response = groq_llm.invoke(prompt)
    response_heading = groq_llm.invoke(prompt1)
    
    heading = getattr(response_heading, "content", str(response_heading)).strip()
    text = getattr(response, "content", str(response))
    subtopics = [re.sub(r'^[-•*\d.\s]+', '', l).strip() for l in text.split("\n") if l.strip()]
    
    return {
        "heading": heading,
        "subtopics": subtopics[:num_subtopics] or [f"Overview of {topic}", "Key Aspects", "Future Outlook"]
    }

def retriever_agent(state: GraphState) -> Dict[str, Any]:
    content = {}
    for sub in state["subtopics"]:
        prompt = f"Write a detailed informative paragraph about '{sub}' in the context of '{state['topic']}'."
        response = groq_llm.invoke(prompt)
        content_text = getattr(response, "content", f"Content for {sub}")
        content[sub] = content_text
    return {"content": content}

def summarizer_agent(state: GraphState) -> Dict[str, Any]:
    summaries = {}
    for sub, text in state["content"].items():
        prompt = f"Summarize this content about '{sub}' into a single coherent paragraph (no bullet points) : {text[:1500]}"
        response = groq_llm.invoke(prompt)
        summaries[sub] = getattr(response, "content", str(response))
    return {"summaries": summaries}

def analyzer_agent(state: GraphState) -> Dict[str, Any]:
    insights = {}
    for sub, summary in state["summaries"].items():
        prompt = f"List 3–4 key insights or takeaways from this text:\n{summary}"
        response = groq_llm.invoke(prompt)
        text = getattr(response, "content", str(response))

        # Clean bullet formatting safely
        cleaned_lines = []
        for l in text.split("\n"):
            l = re.sub(r'(?i)here are.*insights.*', '', l)  # remove "Here are..." lines
            if l.strip():
                line_clean = re.sub(r'^[-•*\d.\s]+', '', l).strip()
                cleaned_lines.append(f"- {line_clean}")
        cleaned = "\n".join(cleaned_lines)

        insights[sub] = cleaned.strip()
    return {"insights": insights}

           

def clean_text(text: str) -> str:
    """Remove markdown and unwanted characters while keeping word spacing."""
    # Remove markdown symbols but preserve spacing
    text = re.sub(r'[*_`#>\-]+', '', text)
    text = re.sub(r'\s+', ' ', text)  # normalize whitespace
    return text.strip()


def clean_markdown(text: str) -> str:
    """Basic markdown cleaner for conclusion."""
    return clean_text(text)


def report_agent(state: dict) -> dict:
    """Generate PDF in memory (not saved to disk) and return Base64-encoded string."""

    buffer = BytesIO()

    # Setup PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    title_style = styles["Title"]
    title_bold_style = ParagraphStyle(
        "TitleBold", parent=title_style, fontName="Helvetica-Bold"
    )
    q_style = ParagraphStyle(
        "Subtopic", parent=styles["Heading2"], fontSize=11, leading=13, spaceAfter=4
    )
    a_style = ParagraphStyle(
        "Content", parent=styleN, fontSize=9, leading=11, spaceAfter=6
    )

    # --- Build Content ---
    content = []

    # Title
    title_clean = re.sub(r'["""*:-]+', "", state.get("heading", "")).strip()
    content.append(Paragraph(f"<b>{title_clean}</b>", title_bold_style))
    content.append(Spacer(1, 12))

    # Introduction
    intro_text = clean_text(state.get("intro", ""))
    content.append(Paragraph("<b>Introduction:</b>", q_style))
    content.append(Paragraph(intro_text, a_style))
    content.append(Spacer(1, 10))

    # Subtopics, Summaries & Insights
    for i, sub in enumerate(state.get("summaries", {}), 1):
        # Add page break after 1st subtopic, then after every 2 subtopics
        # i=1: no break (page 1 with intro)
        # i=2: break before (starts page 2)
        # i=3: no break (page 2)
        # i=4: break before (starts page 3)
        # i=5: no break (page 3)
        # i=6: break before (starts page 4)
        # Pattern: break if i > 1 AND (i-1) is even
        if i > 1 and (i - 1) % 2 == 1:
            content.append(PageBreak())
        
        # 🧹 Clean subtopic name
        sub_clean = re.sub(r'["""*•\-]+', '', sub).strip()
        if sub_clean:
            heading_text = f"<b>{i}. {sub_clean}:</b>"
            content.append(Paragraph(heading_text, q_style))

        # 🧹 Clean summary
        summary_text = clean_text(state["summaries"][sub])
        content.append(Paragraph(summary_text, a_style))

        # 🧹 Add insights (with heading)
        if sub in state.get("insights", {}):
            insights_text = state["insights"][sub]
            cleaned_lines = []
            for line in insights_text.split("\n"):
                line = re.sub(r"(?i)here\s+are.*insights.*", "", line).strip()
                line = clean_text(line)
                if line:
                    cleaned_lines.append(line)

            if cleaned_lines:
                content.append(Paragraph("<b>Insights:</b>", a_style))
                for line in cleaned_lines:
                    content.append(Paragraph(line, a_style))

        content.append(Spacer(1, 4))

    # --- Conclusion ---
    content.append(PageBreak())
    content.append(Paragraph("<b>Conclusion:</b>", q_style))
    conclusion_text = clean_markdown(
        state.get("conclusion", "Conclusion not available.")
    )
    content.append(Paragraph(conclusion_text, a_style))
    content.append(Spacer(1, 20))

    # --- Visual Summary ---
    if "visualizations" in state and state["visualizations"]:
        content.append(Paragraph("<b>Visual Summary:</b>", q_style))
        for img_path in state["visualizations"]:
            content.append(Spacer(1, 8))
            content.append(Image(img_path, width=450, height=250))

    # --- Page Number Footer ---
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        canvas.drawRightString(200 * mm, 10 * mm, f"{page_num}")

    # Build PDF in memory
    doc.build(content, onFirstPage=add_page_number, onLaterPages=add_page_number)

    pdf_data = buffer.getvalue()
    buffer.close()

    pdf_base64 = base64.b64encode(pdf_data).decode("utf-8")

    return {"pdf_base64": pdf_base64}


def conclusion_agent(state: GraphState) -> Dict[str, Any]:
    """Generate a concise conclusion summarizing the entire topic."""
    combined_text = " ".join(state["summaries"].values())
    prompt = (
        f"Write a strong concluding paragraph (around 120–150 words) give direct conclusion not any intorduction line that here ia the conclusion "
        f"that summarizes the key insights and future outlook for the topic '{state['topic']}'.\n"
        f"Here is the context:\n{combined_text[:2000]}"
    )
    response = groq_llm.invoke(prompt)
    return {"conclusion": getattr(response, "content", str(response))}

# ==========================
# --- Build Workflow ---
# ==========================
graph = StateGraph(GraphState)
graph.add_node("intro", intro_agent)
graph.add_node("planner", planner_agent)
graph.add_node("retriever", retriever_agent)
graph.add_node("summarizer", summarizer_agent)
graph.add_node("analyzer", analyzer_agent)

graph.add_node("report_generator", report_agent)
graph.add_node("conclusion", conclusion_agent)

graph.add_edge(START, "intro")
graph.add_edge("intro", "planner")
graph.add_edge("planner", "retriever")
graph.add_edge("retriever", "summarizer")
graph.add_edge("summarizer", "analyzer")
graph.add_edge("analyzer", "conclusion")
graph.add_edge("conclusion","report_generator")
graph.add_edge("report_generator", END)

app = graph.compile()

# ==========================
# --- Run Workflow ---
# ==========================
if __name__ == "__main__":
    topic = input("Enter research topic: ").strip()
    final_state = None

    for state in app.stream({"topic": topic}):
        final_state = state
        if "report_generator" in state:
            print("\n📄 Report generation in progress...")

    if final_state and "report_generator" in final_state:
        pdf_path = final_state["report_generator"].get("pdf_path")
        print(f"\n✅ Report generated successfully: {pdf_path}")
    else:
        print("⚠️ Something went wrong: report not generated.")