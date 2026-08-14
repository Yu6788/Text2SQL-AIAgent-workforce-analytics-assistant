from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.runtime import RuntimeOptions, run_question  # noqa: E402


QUESTION_GROUPS = {
    "Headcount": [
        ("Active employees by business unit", "How many active employees are in each business unit?"),
        ("Largest organization", "Which organization has the highest active headcount?"),
    ],
    "Talent Reviews": [
        ("2026 H1 review completion", "What was the 2026 H1 talent review completion rate?"),
        (
            "Performance by business unit",
            "Which business unit had the highest average performance rating in 2026 H1?",
        ),
    ],
    "Development Programs": [
        ("Best completion rate", "Which development program had the highest completion rate?"),
        (
            "Leadership program correlation",
            "Did employees who completed Leadership Development programs have a higher later promotion rate?",
        ),
    ],
    "Mobility": [
        ("Q2 2026 promotions", "How many employees were promoted in Q2 2026?"),
        ("Annual mobility trend", "What was the annual internal mobility trend from 2024 through 2026?"),
    ],
    "Demo Paths": [
        ("Repair: unsafe SQL", "Repair demo unsafe: how many active employees are there?"),
        ("Repair: bad column", "Repair demo bad column: count employees by employment status."),
        ("Guardrail rejection", "What is the weather today?"),
    ],
}

DEFAULT_QUESTION = "How many active employees are in each business unit?"

MAIN_EXAMPLE_QUESTIONS = [
    "How many active employees are in each business unit?",
    "Which organization has the highest active headcount?",
    "What was the 2026 H1 talent review completion rate?",
    "Which business unit had the best 2026 H1 reviews?",
    "Which development program had the highest completion rate?",
    "Did Leadership Development completion correlate with later promotions?",
    "How many employees were promoted in Q2 2026?",
    "What was the annual internal mobility trend from 2024 through 2026?",
    "What percentage of active employees is in each business unit?",
]

SCHEMA_SUMMARY = [
    {
        "table": "employees",
        "grain": "one employee",
        "what_it_answers": "active headcount, status, hire/termination dates, job level, job family, organization assignment",
    },
    {
        "table": "organizations",
        "grain": "one organization",
        "what_it_answers": "business unit, region, organization status, leader, organization-level grouping",
    },
    {
        "table": "talent_reviews",
        "grain": "one employee review cycle",
        "what_it_answers": "review completion, performance ratings, potential ratings, promotion recommendations",
    },
    {
        "table": "development_programs",
        "grain": "one program",
        "what_it_answers": "program catalog, program type, target job level, program status",
    },
    {
        "table": "employee_programs",
        "grain": "one employee-program enrollment",
        "what_it_answers": "program enrollment, completion status, completion date, completion score",
    },
    {
        "table": "internal_moves",
        "grain": "one internal move event",
        "what_it_answers": "promotions, lateral transfers, organization transfers, role changes, mobility trends",
    },
]

METRIC_DEFINITIONS = [
    {
        "metric": "Active headcount",
        "definition": "Employees where employment_status = 'Active'. For point-in-time questions, use hire and termination dates.",
    },
    {
        "metric": "Review completion rate",
        "definition": "Completed reviews divided by non-cancelled reviews for the selected review cycle.",
    },
    {
        "metric": "Program completion rate",
        "definition": "Completed enrollments divided by non-withdrawn enrollments.",
    },
    {
        "metric": "Promotion rate",
        "definition": "Unique employees with a Promotion internal move divided by the chosen eligible workforce denominator.",
    },
    {
        "metric": "Internal mobility rate",
        "definition": "Unique employees with at least one qualifying internal move divided by the selected workforce denominator.",
    },
    {
        "metric": "High performance",
        "definition": "Talent review performance_rating >= 4.",
    },
]

PIPELINE_STEPS = [
    ("Guardrail", "guardrail_allowed"),
    ("Retrieval", "retrieved_tables"),
    ("SQL", "generated_sql"),
    ("Validation", "validation_result"),
    ("DuckDB", "db_result"),
    ("Answer", "final_answer"),
]


st.set_page_config(
    page_title="Workforce Text-to-SQL Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --ink: #f8fafc;
        --muted: #aab2ba;
        --line: #293038;
        --panel: #12161a;
        --soft: #0b0e11;
        --shell: #0c0f11;
        --shell-2: #15191c;
        --accent: #5dd6c7;
        --accent-dark: #0f766e;
        --warn: #b45309;
        --danger: #b91c1c;
      }
      .stApp {
        background: #080a0c;
        color: #f8fafc;
        height: 100vh;
        overflow: hidden;
        overflow-x: hidden;
      }
      html, body, main, header, footer,
      [data-testid="stAppViewContainer"],
      [data-testid="stHeader"],
      [data-testid="stToolbar"],
      [data-testid="stDecoration"],
      [data-testid="stStatusWidget"],
      [data-testid="stBottomBlockContainer"],
      [data-testid="stBottom"] {
        background: #080a0c !important;
        color: #f8fafc !important;
      }
      html, body,
      [data-testid="stAppViewContainer"],
      [data-testid="stMain"],
      main {
        height: 100vh !important;
        overflow: hidden !important;
        overflow-x: hidden !important;
      }
      * {
        box-sizing: border-box;
      }
      [data-testid="stHeader"]::before,
      [data-testid="stHeader"]::after {
        background: #080a0c !important;
      }
      #MainMenu,
      footer,
      [data-testid="stToolbar"],
      [data-testid="stDecoration"],
      [data-testid="stDeployButton"],
      [data-testid="stHeaderActionElements"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
      }
      [data-testid="stHeader"] {
        height: 0 !important;
        min-height: 0 !important;
      }
      .block-container {
        max-width: 1280px;
        width: 100%;
        padding-top: 0.45rem;
        padding-bottom: 0.45rem;
        height: 100vh;
        overflow: hidden;
        overflow-x: hidden;
      }
      section[data-testid="stSidebar"] {
        background: #080a0c;
        border-right: 1px solid #232a31;
        height: 100vh;
        overflow-y: auto;
        display: block !important;
        visibility: visible !important;
        min-width: 20rem !important;
        width: 20rem !important;
        transform: translateX(0) !important;
      }
      section[data-testid="stSidebar"][aria-expanded="false"] {
        display: block !important;
        visibility: visible !important;
        min-width: 20rem !important;
        width: 20rem !important;
        transform: translateX(0) !important;
      }
      section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
        height: 0.8rem !important;
        min-height: 0.8rem !important;
        padding: 0 !important;
        margin: 0 !important;
      }
      section[data-testid="stSidebar"] > div {
        padding-top: 0.2rem !important;
      }
      section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding-top: 0.25rem !important;
        margin-top: 0 !important;
      }
      section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
      }
      section[data-testid="stSidebar"] h1:first-child,
      section[data-testid="stSidebar"] h2:first-child,
      section[data-testid="stSidebar"] h3:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
      }
      [data-testid="collapsedControl"],
      button[kind="header"],
      [data-testid="stSidebarCollapseButton"],
      [data-testid="stSidebarNavCollapseButton"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
      }
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        color: #f4f2ed;
        letter-spacing: 0;
      }
      section[data-testid="stSidebar"] p,
      section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] span {
        color: #d5d9dc;
      }
      section[data-testid="stSidebar"] .stCaptionContainer,
      section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #9aa3aa;
      }
      section[data-testid="stSidebar"] div[data-testid="stExpander"] {
        background: #15191c;
        border-color: #2a3035;
      }
      .sidebar-card {
        background: #0b0f16;
        border: 1px solid #223041;
        border-radius: 8px;
        padding: 0.65rem;
        margin: 0.55rem 0;
      }
      .sidebar-card strong {
        color: #f8fafc;
        display: block;
        font-size: 0.82rem;
        margin-bottom: 0.22rem;
      }
      .sidebar-card span {
        color: #aab2ba;
        display: block;
        font-size: 0.75rem;
        line-height: 1.35;
      }
      .chat-panel {
        background: #080a0c;
        border: 1px solid #2d5267;
        border-radius: 8px;
        padding: 0.85rem;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
      }
      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #080a0c !important;
        border: 1px solid #2d5267 !important;
        border-radius: 8px !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        max-width: 100% !important;
        overflow-x: hidden !important;
      }
      div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background: #080a0c !important;
        min-height: 100% !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
      }
      .chat-panel-title {
        color: #f8fafc;
        font-size: 0.95rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        padding-bottom: 0.55rem;
        border-bottom: 1px solid #1f2a36;
      }
      .ask-module {
        margin-bottom: 0.34rem;
      }
      .ask-module-title {
        color: #f8fafc;
        font-size: 0.95rem;
        font-weight: 750;
        line-height: 1.08;
        margin: 0;
      }
      .ask-list {
        margin-top: 0.16rem;
      }
      .ask-list div[data-testid="stHorizontalBlock"] {
        gap: 0.35rem !important;
      }
      .ask-list div[data-testid="column"] {
        padding: 0 !important;
      }
      .ask-list div[data-testid="stButton"] > button {
        height: 2.22rem;
        min-height: 2.22rem;
        max-height: 2.22rem;
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        overflow: hidden;
        line-height: 1.12;
        padding: 0.22rem 0.48rem;
        border-radius: 8px;
        border-color: #2d5267;
        background: #07111c;
        color: #f8fafc;
        font-size: 0.74rem;
      }
      .ask-list div[data-testid="stButton"] > button p {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: normal;
        margin: 0;
      }
      .ask-list div[data-testid="stButton"] > button:hover {
        border-color: #5dd6c7;
        background: #0b2430;
        color: #ffffff;
      }
      [data-testid="stMetric"] {
        background: #11161a;
        border: 1px solid #293038;
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
        box-shadow: none;
      }
      [data-testid="stMetricValue"] {
        color: #f8fafc;
        font-size: 1.25rem;
      }
      div[data-testid="stExpander"] {
        border: 1px solid #293038;
        border-radius: 8px;
        background: #11161a;
      }
      .stButton > button,
      .stFormSubmitButton > button {
        border-radius: 7px;
        border: 1px solid #3a434c;
        font-weight: 600;
        background: #0b0e11;
        color: #f8fafc;
      }
      .stButton > button:hover,
      .stFormSubmitButton > button:hover {
        border-color: #5dd6c7;
        color: #e6fffb;
        background: #11161a;
      }
      .stFormSubmitButton > button[kind="primary"] {
        background: #000000;
        border-color: #5dd6c7;
        color: #ffffff;
      }
      .stTextArea textarea {
        border-radius: 8px;
        border-color: #3a434c;
        background: #0b0e11;
        color: #f8fafc;
      }
      .stSelectbox div[data-baseweb="select"],
      .stRadio,
      .stCheckbox {
        color: #f8fafc;
      }
      div[data-baseweb="select"] > div {
        background: #0b0e11;
        border-color: #3a434c;
        color: #f8fafc;
      }
      div[data-testid="stForm"] {
        background: #11161a;
        border: 1px solid #293038;
        border-radius: 8px;
        padding: 0.85rem 0.95rem 1rem 0.95rem;
      }
      .pipeline-row {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.45rem;
        margin: 0.5rem 0 1.05rem 0;
      }
      .pipeline-step {
        border: 1px solid #293038;
        border-radius: 8px;
        padding: 0.62rem 0.65rem;
        font-size: 0.82rem;
        font-weight: 700;
        text-align: center;
        background: #11161a;
        color: #d6dce2;
      }
      .pipeline-step.done {
        border-color: #5dd6c7;
        background: #0f2a2a;
        color: #bff7ef;
      }
      .pipeline-step.failed {
        border-color: #ef4444;
        background: #240b0d;
        color: #fecaca;
      }
      div[data-testid="stDataFrame"] {
        border: 1px solid #293038;
        border-radius: 8px;
        overflow: hidden;
      }
      .stMarkdown, .stCaptionContainer, p, li, label {
        color: #d6dce2;
      }
      h1, h2, h3, h4, h5, h6 {
        color: #f8fafc;
      }
      div[data-testid="stAlert"] {
        background: #0b0e11;
        border: 1px solid #293038;
        color: #f8fafc;
        border-radius: 8px;
      }
      div[data-testid="stAlert"] * {
        color: #f8fafc;
      }
      .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
      }
      .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
        color: #d6dce2;
        background: #0f1317;
      }
      .stTabs [aria-selected="true"] {
        color: #ffffff;
        background: #151b20;
      }
      .section-note { color: #6b7280; font-size: 0.85rem; }
      .chat-thread {
        display: flex;
        flex-direction: column;
        gap: 0.78rem;
        margin: 0.3rem 0 1.2rem 0;
      }
      .chat-row {
        display: flex;
        width: 100%;
      }
      .chat-row.user {
        justify-content: flex-end;
      }
      .chat-row.assistant {
        justify-content: flex-start;
      }
      .chat-bubble {
        max-width: min(760px, 82%);
        border-radius: 8px;
        padding: 0.78rem 0.92rem;
        color: #f8fafc;
        font-size: 0.95rem;
        line-height: 1.48;
        border: 1px solid #26384a;
        box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22);
      }
      .chat-row.user .chat-bubble {
        background: #082033;
        border-color: #2f81a7;
        color: #ffffff;
      }
      .chat-row.assistant .chat-bubble {
        background: #0b0f16;
        border-color: #26384a;
      }
      .chat-bubble p {
        margin: 0;
        color: #f8fafc;
      }
      .chat-note {
        margin-top: 0.45rem;
        color: #9fded7;
        font-size: 0.88rem;
      }
      [data-testid="stChatMessage"] {
        background: #0b0f16 !important;
        border: 1px solid #26384a;
        border-radius: 8px;
        padding: 0.45rem 0.7rem;
        margin-bottom: 0.7rem;
        color: #f8fafc;
      }
      [data-testid="stChatMessage"] > div,
      [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
      [data-testid="stChatMessage"] p,
      [data-testid="stChatMessage"] span {
        background: transparent !important;
        color: #f8fafc !important;
      }
      [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #080a0c !important;
        border-color: #344256;
      }
      [data-testid="stChatMessageAvatarUser"],
      [data-testid="stChatMessageAvatarAssistant"],
      [data-testid="chatAvatarIcon-user"],
      [data-testid="chatAvatarIcon-assistant"] {
        background: #111827 !important;
        color: #f8fafc !important;
        border: 1px solid #334155;
      }
      [data-testid="stChatInput"] {
        background: #080a0c !important;
      }
      [data-testid="stChatInput"] > div,
      [data-testid="stChatInput"] form,
      [data-testid="stChatInput"] div {
        background: transparent !important;
      }
      [data-testid="stChatInput"] > div {
        border: 1px solid #5dd6c7 !important;
        border-radius: 10px !important;
        background: #07111c !important;
        box-shadow: 0 0 0 1px rgba(93, 214, 199, 0.18), 0 16px 34px rgba(0, 0, 0, 0.42);
        overflow: hidden;
      }
      [data-testid="stChatInput"] textarea {
        background: #07111c !important;
        border: 0 !important;
        box-shadow: none !important;
        color: #f8fafc !important;
        caret-color: #5dd6c7;
      }
      [data-testid="stChatInput"] textarea::placeholder {
        color: #93a4b5 !important;
      }
      [data-testid="stChatInput"] button {
        background: transparent !important;
        border: 0 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        box-shadow: none !important;
        margin-right: 0.28rem !important;
        width: 2.35rem !important;
        height: 2.35rem !important;
        padding: 0 !important;
      }
      [data-testid="stChatInput"] button:hover,
      [data-testid="stChatInput"] button:focus,
      [data-testid="stChatInput"] button:active {
        background: #10202a !important;
        border: 0 !important;
        box-shadow: none !important;
        outline: none !important;
      }
      [data-testid="stChatInput"] button svg {
        color: #ffffff !important;
        fill: none !important;
        stroke: #ffffff !important;
      }
      [data-baseweb="popover"],
      [data-baseweb="popover"] > div,
      [data-baseweb="menu"],
      [role="listbox"],
      [role="option"] {
        background: #0b0e11 !important;
        color: #f8fafc !important;
      }
      [data-baseweb="popover"] * {
        color: #f8fafc !important;
      }
      input, textarea, select {
        background-color: #07111c !important;
        color: #f8fafc !important;
      }
      .chat-input-shell {
        border-top: 1px solid #1f2a36;
        margin-top: 0.75rem;
        padding-top: 0.75rem;
      }
      .chat-input-shell div[data-testid="stForm"] {
        background: #07111c !important;
        border: 1px solid #5dd6c7 !important;
        border-radius: 10px !important;
        padding: 0.45rem !important;
        box-shadow: 0 0 0 1px rgba(93, 214, 199, 0.18), 0 16px 34px rgba(0, 0, 0, 0.32);
      }
      .chat-input-shell div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
        align-items: center;
      }
      .chat-input-shell input {
        border: 0 !important;
        background: #07111c !important;
        color: #f8fafc !important;
        box-shadow: none !important;
      }
      .chat-input-shell .stButton > button,
      .chat-input-shell .stFormSubmitButton > button {
        background: #0b2a34 !important;
        border: 0 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        min-height: 2.45rem;
      }
      @media (max-width: 900px) {
        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        main,
        .stApp,
        .block-container {
          height: auto !important;
          overflow: auto !important;
        }
        .intro-grid, .pipeline-row {
          grid-template-columns: 1fr;
        }
        .block-container {
          padding-top: 1rem;
          padding-bottom: 1rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.ask-module-title) {
          height: auto !important;
          min-height: 0 !important;
          max-height: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-panel-title) {
          height: 62vh !important;
          max-height: 62vh !important;
          min-height: 360px !important;
        }
        [data-testid="stChatInput"] {
          left: 0 !important;
          right: 0 !important;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def cached_settings():
    return load_settings(ROOT / "config.yaml")


def status_badge(status: str) -> None:
    if status == "SUCCESS":
        st.success(status)
    elif status in {"REJECTED_BY_GUARDRAIL"}:
        st.warning(status)
    elif status in {"API_ERROR", "DATABASE_EXECUTION_ERROR", "MAX_SQL_RETRIES_EXCEEDED"}:
        st.error(status)
    else:
        st.info(status)


def render_pipeline(state: dict) -> None:
    status = state.get("status", "")
    cells = []
    for label, key in PIPELINE_STEPS:
        done = bool(state.get(key))
        css = "pipeline-step done" if done else "pipeline-step"
        if status in {"API_ERROR", "DATABASE_EXECUTION_ERROR"} and label in {"SQL", "DuckDB", "Answer"} and not done:
            css = "pipeline-step failed"
        cells.append(f'<div class="{css}">{label}</div>')
    st.markdown('<div class="pipeline-row">' + "".join(cells) + "</div>", unsafe_allow_html=True)


def render_retrieved_tables(state: dict) -> None:
    tables = state.get("retrieved_tables") or []
    if not tables:
        st.caption("No schema retrieval ran for this question.")
        return
    rows = []
    for idx, table in enumerate(tables, start=1):
        rows.append(
            {
                "rank": idx,
                "table": table,
                "retrieval_score": state.get("retrieval_scores", {}).get(table),
                "reranker_score": state.get("reranker_scores", {}).get(table),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_db_result(state: dict) -> None:
    result = state.get("db_result")
    if not result:
        st.caption("No database result available.")
        if state.get("db_error"):
            st.error(state["db_error"])
        return
    st.caption(
        f"{result['row_count']} row(s), "
        f"{result['execution_time_ms']:.1f} ms"
        + ("; truncated" if result["truncated"] else "")
    )
    st.dataframe(
        pd.DataFrame(result["rows"], columns=result["columns"]),
        width="stretch",
        hide_index=True,
    )


def render_schema_summary() -> None:
    st.dataframe(pd.DataFrame(SCHEMA_SUMMARY), width="stretch", hide_index=True)
    st.caption("The agent retrieves the top schema documents for each question and passes only those tables to SQL generation.")


def render_immediate_answer(state: dict) -> None:
    st.subheader("Answer")
    if state.get("final_answer"):
        st.success(state["final_answer"])
        return
    status = state.get("status")
    if status == "REJECTED_BY_GUARDRAIL":
        st.warning(state.get("guardrail_reason", "This question is outside the database scope."))
        return
    if state.get("db_error"):
        st.error(str(state["db_error"])[:1200])
        return
    st.info("No final answer was produced for this run.")


def render_chat_bubble(role: str, message: str, note: str = "") -> None:
    safe_message = html.escape(message or "").replace("\n", "<br>")
    safe_note = html.escape(note or "")
    note_html = f'<div class="chat-note">{safe_note}</div>' if safe_note else ""
    st.markdown(
        f"""
        <div class="chat-row {role}">
          <div class="chat-bubble">
            <p>{safe_message}</p>
            {note_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def state_answer_text(state: dict) -> str:
    if state.get("final_answer"):
        return state["final_answer"]
    if state.get("status") == "REJECTED_BY_GUARDRAIL":
        return state.get("guardrail_reason", "This question is outside the database scope.")
    if state.get("db_error"):
        return str(state["db_error"])[:1200]
    return "No final answer was produced for this run."


def render_agent_details(state: dict) -> None:
    render_pipeline(state)

    top_left, top_mid, top_right, top_fourth = st.columns(4)
    with top_left:
        st.metric("Status", state.get("status", "UNKNOWN"))
    with top_mid:
        st.metric("SQL retries", state.get("sql_retry_count", 0))
    with top_right:
        st.metric("Retrieved tables", len(state.get("retrieved_tables", [])))
    with top_fourth:
        row_count = state.get("db_result", {}).get("row_count", 0)
        st.metric("Result rows", row_count)

    status_badge(state.get("status", "UNKNOWN"))

    tabs = st.tabs(
        [
            "Context",
            "Retrieved Tables",
            "Generated SQL",
            "Validation",
            "Database Result",
            "Repair",
        ]
    )
    with tabs[0]:
        st.caption("How this message was interpreted before SQL generation.")
        st.write("Original question:", state.get("user_question", ""))
        resolved_question = state.get("resolved_question")
        if state.get("is_follow_up") and resolved_question:
            st.write("Resolved question:", resolved_question)
            st.caption(state.get("follow_up_reason", ""))
        allowed = state.get("guardrail_allowed")
        st.write("Guardrail allowed:", allowed)
        st.write(state.get("guardrail_reason", ""))
    with tabs[1]:
        st.caption("Top schema context selected for SQL generation. These are the tables the model sees.")
        render_retrieved_tables(state)
    with tabs[2]:
        st.caption("DuckDB SQL produced by the LLM or local stub.")
        sql = state.get("generated_sql")
        if sql:
            st.code(sql, language="sql")
        else:
            st.caption("No SQL generated.")
    with tabs[3]:
        st.caption("Deterministic SQLGlot safety checks before execution.")
        validation = state.get("validation_result")
        if validation:
            if validation.get("is_valid"):
                st.success("SQL validation passed")
            else:
                st.error(validation.get("error_type", "SQL validation failed"))
            st.json(validation)
        else:
            st.caption("No validation result.")
    with tabs[4]:
        st.caption("Read-only DuckDB execution result, capped by the configured row limit.")
        render_db_result(state)
    with tabs[5]:
        st.caption("Bounded SQL repair attempts after validation or database failures.")
        st.write("Retry count:", state.get("sql_retry_count", 0))
        retry_history = state.get("retry_history") or []
        if retry_history:
            for idx, item in enumerate(retry_history, start=1):
                st.code(item, language="text")
        else:
            st.caption("No SQL repair attempts.")


settings = cached_settings()

with st.sidebar:
    st.header("Workforce Analytics Assistant")

    st.subheader("Run Mode")
    mode = st.radio(
        "LLM mode",
        ["Offline Demo", "Live API"],
        index=0,
        help="Offline Demo uses local deterministic rules. Live API uses your configured model key.",
    )
    if mode == "Offline Demo":
        st.caption("Runs locally. No API cost.")
    else:
        st.caption("Uses your DeepSeek/OpenAI-compatible API key.")

    st.subheader("Actions")
    if st.button("Clear chat", width="stretch"):
        st.session_state["chat_turns"] = []
        st.session_state["last_state"] = None

    embedding_backend = "hashing"
    reranker_backend = "lexical"
    skip_retrieval = False

    st.subheader("Info")
    with st.expander("About This Agent", expanded=False):
        st.write(
            "This assistant answers questions about a synthetic workforce analytics database. "
            "It translates natural-language questions into SQL, retrieves relevant table context, "
            "validates queries, executes them in DuckDB, and summarizes the result."
        )
        st.caption("It supports lightweight follow-up questions within the current session.")

    with st.expander("Agentic Framework", expanded=False):
        st.caption("The app uses a small inspectable agent workflow rather than a single black-box prompt.")
        st.markdown("**1. Understand**")
        st.caption("Check whether the question belongs to the workforce analytics scope.")
        st.markdown("**2. Retrieve**")
        st.caption("Select relevant table and metric context before generating SQL.")
        st.markdown("**3. Generate & Validate**")
        st.caption("Create read-only SQL, validate table and column usage, then repair bounded failures.")
        st.markdown("**4. Execute & Summarize**")
        st.caption("Run the SQL in DuckDB and turn the result into a natural-language answer.")

    with st.expander("What You Can Ask", expanded=False):
        st.caption("Best fit questions are aggregate workforce analytics questions, not individual employee lookups.")
        st.markdown("**Good fits**")
        st.caption("Headcount by business unit, organization, status, or time period.")
        st.caption("Talent review completion, performance, potential, and recommendations.")
        st.caption("Development program enrollment, completion, and promotion correlation.")
        st.caption("Internal mobility, promotions, transfers, and role movement trends.")
        st.markdown("**Example follow-ups**")
        st.caption('"What about Technology?"')
        st.caption('"Show percentages instead."')
        st.caption('"Compare that with Sales."')

    with st.expander("Conversation Context", expanded=False):
        st.write(
            "The assistant keeps the current chat session in memory while the page stays open. "
            "After a full first question, short follow-ups can reuse the previous question and answer."
        )
        st.caption("Use Clear chat to start over. Refreshing the page may reset the session state.")

    with st.expander("Edges & Limits", expanded=False):
        st.markdown("**Data boundary**")
        st.caption("Synthetic workforce data only, covering 2024-2026.")
        st.markdown("**Privacy boundary**")
        st.caption("No real employee records, salaries, protected attributes, or private personal data.")
        st.markdown("**Question boundary**")
        st.caption("Not designed for weather, market data, current events, policy advice, or external facts.")
        st.markdown("**Mode boundary**")
        st.caption("Offline Demo is deterministic and limited. Live API is broader but depends on your configured provider.")

    with st.expander("Available Tables", expanded=False):
        st.write("Synthetic workforce analytics for 2024-01-01 through 2026-12-31.")
        st.caption("6 tables: employees, organizations, talent reviews, programs, enrollments, internal moves.")
        for row in SCHEMA_SUMMARY:
            st.markdown(f"**{row['table']}**")
            st.caption(row["what_it_answers"])

    with st.expander("Metric Definitions", expanded=False):
        for item in METRIC_DEFINITIONS:
            st.markdown(f"**{item['metric']}**")
            st.caption(item["definition"])

    with st.expander("Q&A", expanded=False):
        st.markdown("**Is this real employee data?**")
        st.caption("No. The database is fully synthetic and does not contain real employee records or PII.")
        st.markdown("**Can I ask follow-up questions?**")
        st.caption("Yes. Ask a full first question, then use short follow-ups within the same session.")
        st.markdown("**Why does the app show SQL details?**")
        st.caption("The details make the answer inspectable: retrieved tables, generated SQL, validation, and database results.")
        st.markdown("**When should I use Live API mode?**")
        st.caption("Use Live API when you want the configured model to generate answers. Offline Demo runs locally without API cost.")

if "chat_turns" not in st.session_state:
    st.session_state["chat_turns"] = []

chat_question = None
selected_question = None

st.markdown('<div class="ask-module">', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<div class="ask-module-title">What can I ask?</div>', unsafe_allow_html=True)
    st.markdown('<div class="ask-list">', unsafe_allow_html=True)
    visible_examples = MAIN_EXAMPLE_QUESTIONS[:4]
    for row_start in range(0, len(visible_examples), 2):
        cols = st.columns(2)
        for col_idx, example_question in enumerate(visible_examples[row_start : row_start + 2]):
            with cols[col_idx]:
                if st.button(example_question, key=f"main_example_question_{row_start + col_idx}", width="stretch"):
                    selected_question = example_question
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown('<div class="chat-panel-title">Conversation</div>', unsafe_allow_html=True)
    with st.container(height=340, border=False):
        st.markdown('<div class="chat-thread">', unsafe_allow_html=True)
        for turn in st.session_state["chat_turns"]:
            state = turn.get("state")
            render_chat_bubble("user", turn["question"])
            if turn.get("pending") or state is None:
                render_chat_bubble(
                    "assistant",
                    "Thinking...",
                )
                continue
            note = ""
            if state.get("is_follow_up") and state.get("resolved_question"):
                note = f"Interpreted as: {state['resolved_question']}"
            render_chat_bubble("assistant", state_answer_text(state), note=note)
            with st.expander("Show workflow details", expanded=False):
                render_agent_details(state)

        if not st.session_state["chat_turns"]:
            render_chat_bubble(
                "assistant",
                "Ask me a workforce analytics question. You can start with a full question, "
                "then ask a short follow-up.",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="chat-input-shell">', unsafe_allow_html=True)
    with st.form("chat_input_form", clear_on_submit=True):
        input_col, send_col = st.columns([10, 1.25])
        with input_col:
            typed_question = st.text_input(
                "Ask a workforce analytics question",
                placeholder="Ask a workforce analytics question...",
                label_visibility="collapsed",
            )
        with send_col:
            submitted = st.form_submit_button("Send", width="stretch")
        if submitted and typed_question.strip():
            chat_question = typed_question.strip()
    st.markdown("</div>", unsafe_allow_html=True)

question_to_run = chat_question or selected_question

pending_turn = st.session_state.pop("pending_turn", None)

if question_to_run and pending_turn is None:
    st.session_state["chat_turns"].append({"question": question_to_run, "state": None, "pending": True})
    st.session_state["pending_turn"] = question_to_run
    st.rerun()

if pending_turn:
    options = RuntimeOptions(
        llm_provider="stub" if mode == "Offline Demo" else "configured",
        embedding_backend=embedding_backend,
        reranker_backend=reranker_backend,
        skip_retrieval=skip_retrieval,
        env_path=ROOT / ".env",
    )
    thinking_text = "Thinking..."
    with st.spinner(thinking_text):
        previous_state = st.session_state.get("last_state")
        state = run_question(
            settings,
            ROOT,
            pending_turn,
            options,
            previous_state=previous_state,
            force_follow_up=False,
        )
    st.session_state["last_state"] = state
    if st.session_state["chat_turns"] and st.session_state["chat_turns"][-1].get("pending"):
        st.session_state["chat_turns"][-1] = {"question": pending_turn, "state": state, "pending": False}
    else:
        st.session_state["chat_turns"].append({"question": pending_turn, "state": state, "pending": False})
    st.rerun()
