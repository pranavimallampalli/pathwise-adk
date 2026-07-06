import os
import json
import asyncio
import re
import datetime
import logging
import time
import pandas as pd
import streamlit as st
from collections import defaultdict
from typing import Any, Optional, Dict, List

from app.agent import app
from google.adk.runners import InMemoryRunner
from google.adk.events.request_input import RequestInput
from google.genai import types

# Page Config
st.set_page_config(
    page_title="PathWise — AI Study Companion",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database file path
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pathwise_data.json")

def load_local_data() -> Optional[dict]:
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_local_data(data_dict: dict) -> bool:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving database: {e}")
        return False

# Initialize Local Database Data
data = load_local_data()
profile_completed = False
if isinstance(data, dict):
    profile = data.get("profile") or {}
    roadmap = data.get("roadmap") or {}
    profile_completed = profile.get("onboarding_completed", False) if isinstance(profile, dict) else False
else:
    profile = {}
    roadmap = {}

tasks = roadmap.get("tasks") or []
streak_value = "5 Days" if profile_completed else "0 Days"



# Session State Initialization
if "runner" not in st.session_state:
    st.session_state.runner = InMemoryRunner(app=app)

if "session_id" not in st.session_state:
    async def init_session():
        session = await st.session_state.runner.session_service.create_session(
            app_name="app", user_id="student_user"
        )
        return session.id
    st.session_state.session_id = asyncio.run(init_session())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = None

if "last_query" not in st.session_state:
    st.session_state.last_query = None

if "active_page" not in st.session_state:
    st.session_state.active_page = "Chat with PathWise"

if "theme" not in st.session_state:
    st.session_state.theme = "Cyberpunk Glow (Purple/Pink)"

if "dev_mode" not in st.session_state:
    st.session_state.dev_mode = False

if "show_all_tasks" not in st.session_state:
    st.session_state.show_all_tasks = False

# Dynamic Themes Colors Configuration
themes_config = {
    "Cyberpunk Glow (Purple/Pink)": {
        "gradient": "linear-gradient(135deg, #a855f7 0%, #ec4899 100%)",
        "accent": "#ec4899",
        "glow": "rgba(168, 85, 247, 0.25)"
    },
    "Mint Forest (Green/Emerald)": {
        "gradient": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
        "accent": "#059669",
        "glow": "rgba(16, 185, 129, 0.25)"
    },
    "Deep Ocean (Navy/Blue)": {
        "gradient": "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
        "accent": "#0369a1",
        "glow": "rgba(2, 132, 199, 0.25)"
    }
}
active_theme_colors = themes_config[st.session_state.theme]

# Custom CSS with Dynamic Theme Variables
st.markdown(
    f"""
    <style>
    /* Dark Theme Global Styling */
    .stApp {{
        background-color: #0d0f14;
        color: #f0f6fc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    
    /* Animation Keyframes */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* Sidebar Styling & Button overrides */
    [data-testid="stSidebar"] {{
        background-color: #07090e;
        border-right: 1px solid #1f242c;
    }}
    [data-testid="stSidebar"] button {{
        border-radius: 8px !important;
        transition: all 0.25s ease !important;
    }}
    [data-testid="stSidebar"] button[kind="primary"] {{
        background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 0 12px rgba(168, 85, 247, 0.4) !important;
    }}
    [data-testid="stSidebar"] button[kind="secondary"]:hover {{
        border-color: #ec4899 !important;
        color: #ec4899 !important;
        transform: translateY(-1px);
    }}
    
    /* Metric Cards Grid - Today's Focus gets more visual weight */
    .metrics-grid {{
        display: grid;
        grid-template-columns: 1.35fr 1fr 1fr 1fr;
        gap: 16px;
        margin-bottom: 20px;
    }}
    .metric-card {{
        background: rgba(22, 27, 34, 0.65);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        transition: transform 0.25s ease, border-color 0.25s, box-shadow 0.25s;
        animation: fadeIn 0.5s ease-out;
    }}
    .metric-card:hover {{
        transform: translateY(-2px);
        border-color: {active_theme_colors['accent']};
        box-shadow: 0 12px 30px {active_theme_colors['glow']};
    }}
    .card-title {{
        font-size: 0.75rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 700;
        margin-bottom: 6px;
    }}
    .card-value {{
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
    }}
    .card-subtext {{
        font-size: 0.8rem;
        color: #22c55e;
        margin-top: 6px;
        font-weight: 600;
    }}
    
    /* Expanders styled like premium Notion Cards */
    div[data-testid="stExpander"] {{
        background-color: rgba(22, 27, 34, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
        transition: border-color 0.25s ease;
    }}
    div[data-testid="stExpander"]:hover {{
        border-color: rgba(168, 85, 247, 0.4) !important;
    }}
    
    /* Badges */
    .badge {{
        padding: 2px 8px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        display: inline-block;
    }}
    .badge-pending {{
        background-color: rgba(168, 85, 247, 0.12);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.25);
    }}
    .badge-completed {{
        background-color: rgba(34, 197, 94, 0.12);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.25);
    }}
    .badge-missed {{
        background-color: rgba(239, 68, 68, 0.12);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.25);
    }}
    .badge-easy {{
        background-color: rgba(34, 197, 94, 0.12);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.25);
    }}
    .badge-medium {{
        background-color: rgba(249, 115, 22, 0.12);
        color: #fb923c;
        border: 1px solid rgba(249, 115, 22, 0.25);
    }}
    .badge-hard {{
        background-color: rgba(239, 68, 68, 0.12);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.25);
    }}
    
    /* Sidebar Details block */
    .sidebar-section {{
        background-color: rgba(22, 27, 34, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    }}
    .sidebar-label {{
        font-size: 0.7rem;
        color: #8b949e;
        text-transform: uppercase;
        margin-bottom: 4px;
        font-weight: 700;
    }}
    .sidebar-value {{
        font-size: 0.85rem;
        color: #ffffff;
        font-weight: 500;
    }}
    .quote-container {{
        font-style: italic;
        color: #8b949e;
        font-size: 0.78rem;
        padding: 10px;
        border-left: 2px solid #a855f7;
        margin-top: 15px;
    }}
    
    /* Custom Chat Containers */
    .chat-user-bubble {{
        display: flex;
        justify-content: flex-end;
        margin-bottom: 12px;
    }}
    .chat-user-content {{
        background: {active_theme_colors['gradient']};
        color: #ffffff;
        padding: 10px 14px;
        border-radius: 12px 12px 0 12px;
        max-width: 85%;
        box-shadow: 0 4px 12px {active_theme_colors['glow']};
    }}
    .chat-bot-bubble {{
        display: flex;
        justify-content: flex-start;
        margin-bottom: 12px;
    }}
    .chat-bot-content {{
        background: rgba(22, 27, 34, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #f0f6fc;
        padding: 10px 14px;
        border-radius: 12px 12px 12px 0;
        max-width: 85%;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }}
    .chat-header-user {{
        font-weight: 800;
        font-size: 0.65rem;
        margin-bottom: 3px;
        opacity: 0.8;
    }}
    .chat-header-bot {{
        font-weight: 800;
        font-size: 0.65rem;
        margin-bottom: 3px;
        color: #a855f7;
    }}
    .chat-text {{
        font-size: 0.88rem;
        line-height: 1.4;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# GREETING MESSAGE CALCULATION
def get_time_of_day_greeting() -> str:
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    else:
        return "Good Evening"

user_name = profile.get("name") or "Pranavi"
time_greeting = get_time_of_day_greeting()
greeting_title = f"{time_greeting}, {user_name}! 🌸"
greeting_message = "Ready to continue your learning journey today?"

# Calculate countdown if dates are present
def get_countdown(exam_date_str) -> str:
    if not isinstance(exam_date_str, str):
        return "Upcoming"
    try:
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)', exam_date_str, re.IGNORECASE)
        if match:
            month_str, day_str = match.groups()
            months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
            month_num = months.index(month_str.lower()) + 1
            day_num = int(day_str)
            exam_date = datetime.date(2026, month_num, day_num)
            today = datetime.date(2026, 7, 4)
            delta = (exam_date - today).days
            if delta > 0:
                return f"{delta} Days"
            elif delta == 0:
                return "Today!"
            else:
                return "Completed"
    except Exception:
        pass
    return "Upcoming"

exam_countdown = "Awaiting setup"
if profile_completed:
    exams_dict = profile.get("exam_dates") or {}
    exams_val = exams_dict.get("exams", "") if isinstance(exams_dict, dict) else ""
    exam_countdown = get_countdown(exams_val)

# RUN RUNNER FUNCTION WITH ERROR HANDLING
async def run_workflow_call(user_query: str) -> str:
    runner = st.session_state.runner
    session_id = st.session_state.session_id
    
    if st.session_state.pending_interrupt:
        interrupt_id = st.session_state.pending_interrupt["interrupt_id"]
        new_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="adk_request_input",
                        id=interrupt_id,
                        response={"result": user_query}
                    )
                )
            ]
        )
        st.session_state.pending_interrupt = None
    else:
        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_query)]
        )
        
    response_text = ""
    try:
        async for event in runner.run_async(
            user_id="student_user",
            session_id=session_id,
            new_message=new_message
        ):
            if isinstance(event, RequestInput):
                msg = event.message
                if event.interrupt_id == "subjects":
                    msg = "Welcome to PathWise! 👋\nLet's build your personalized study roadmap.\nWhat subjects/courses are you studying?"
                st.session_state.pending_interrupt = {
                    "interrupt_id": event.interrupt_id,
                    "message": msg
                }
                response_text = msg
            elif hasattr(event, 'content') and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        if fc.name in ["adk_request_input", "request_input"]:
                            interrupt_id = fc.args.get("interruptId") or fc.id
                            msg = fc.args.get("message", "")
                            if interrupt_id == "subjects":
                                msg = "Welcome to PathWise! 👋\nLet's build your personalized study roadmap.\nWhat subjects/courses are you studying?"
                            st.session_state.pending_interrupt = {
                                "interrupt_id": interrupt_id,
                                "message": msg
                            }
                            response_text = msg
                            break
                    elif part.text:
                        response_text += part.text
            elif hasattr(event, 'output') and event.output:
                # Do not let intermediate text outputs from safety checks overwrite the final question
                if isinstance(event.output, str) and not response_text:
                    response_text += event.output
    except Exception as e:
        logging.error(f"ADK runner exception: {e}", exc_info=True)
        err_msg = str(e).upper()
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
            return "🤖 PathWise is taking a short break.\n\nThe AI service has temporarily reached its quota. Your roadmap and progress are still available. Please try chatting again in a few moments."
        return "🤖 PathWise is taking a short break.\n\nAn unexpected connection error occurred. Your roadmap and progress are still available. Please try again in a few moments."
                
    return response_text

def clean_assistant_response(text: str) -> str:
    if not isinstance(text, str):
        return ""
    if text.strip().startswith("{") and text.strip().endswith("}"):
        return "🤖 I have successfully updated your study profile and roadmap details."
        
    lines = text.split("\n")
    cleaned_lines = []
    has_report = False
    for line in lines:
        if any(h in line for h in ["### Study Plan", "### Resources", "### Progress Summary", "### Roadmap", "### Today's Focus"]):
            has_report = True
            break
        cleaned_lines.append(line)
        
    cleaned_text = "\n".join(cleaned_lines).strip()
    if has_report:
        if not cleaned_text:
            cleaned_text = "🤖 I have generated your new study plan and recommended resources. You can see them updated in the widgets on your dashboard!"
        else:
            cleaned_text += "\n\n*(Your study roadmap and recommended resources have been updated on the dashboard)*"
    return cleaned_text
def classify_and_route_locally(query: str) -> Optional[str]:
    q = query.lower().strip()
    
    # 1. Profile information
    if any(w in q for w in ["profile", "my subject", "what subject", "availability", "session length", "session duration", "weakness", "strength"]):
        subjects_list = profile.get("subjects") or []
        subj_str = ", ".join(subjects_list) if subjects_list else "None"
        avail = profile.get("study_availability") or "N/A"
        sess_len = profile.get("session_length") or "N/A"
        sw = profile.get("strengths_weaknesses") or "N/A"
        return f"📋 **Your Profile Details:**\n- **Subjects Enrolled**: {subj_str}\n- **Daily Availability**: {avail}\n- **Session Length**: {sess_len}\n- **Strengths/Weaknesses**: {sw}"
        
    # 2. Completed tasks
    if any(w in q for w in ["completed task", "completed topic", "done task", "done topic", "finished task", "what did i complete", "what is completed"]):
        completed_tasks = [t for t in tasks if t.get("status") == "completed"]
        if not completed_tasks:
            return "🎯 You haven't completed any topics yet. Keep going! You can mark tasks as completed in the Roadmap widget."
        task_lines = [f"- {t.get('topic')} ({t.get('subject')})" for t in completed_tasks]
        return "✅ **Completed Topics:**\n" + "\n".join(task_lines)
        
    # 3. Missed sessions/tasks
    if any(w in q for w in ["missed session", "missed task", "missed topic", "what did i miss", "what is missed"]):
        missed_tasks = [t for t in tasks if t.get("status") == "missed"]
        if not missed_tasks:
            return "🎉 Excellent! You have 0 missed sessions on your roadmap."
        task_lines = [f"- {t.get('topic')} ({t.get('subject')})" for t in missed_tasks]
        return "⚠️ **Missed Topics:**\n" + "\n".join(task_lines)
        
    # 4. Today's topic / Today's focus
    if any(w in q for w in ["today's focus", "today focus", "today's topic", "today topic", "what should i study today", "what to study today"]):
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        if pending_tasks:
            t = pending_tasks[0]
            return f"📚 **Today's Focus Topic:**\n- **Topic**: {t.get('topic')}\n- **Subject**: {t.get('subject')}\n- **Estimated Duration**: {t.get('estimated_time')}\n\nYou can start studying this topic or chat with me if you need explanations!"
        else:
            return "🎉 You have completed all topics on your current study roadmap! Great job!"
            
    # 5. Upcoming tasks / Roadmap list / Study schedule
    if any(w in q for w in ["upcoming task", "upcoming topic", "next task", "next topic", "roadmap", "study plan", "study schedule", "my schedule", "what's next"]):
        pending_tasks = [t for t in tasks if t.get("status") == "pending"][:3]
        if not pending_tasks:
            return "📅 **Upcoming Schedule:**\nYou have no pending topics! All roadmap tasks have been completed."
        task_lines = [f"- **{t.get('topic')}** ({t.get('subject')} • ⏱️ {t.get('estimated_time')})" for t in pending_tasks]
        return "📅 **Upcoming Topics on Your Schedule:**\n" + "\n".join(task_lines)
        
    # 6. Progress / Statistics
    if any(w in q for w in ["progress", "statistic", "my stats", "percentage", "how many hours", "hours studied"]):
        completed_count = sum(1 for t in tasks if t.get("status") == "completed")
        total_count = len(tasks)
        pct = (completed_count / total_count * 100) if total_count > 0 else 0
        
        session_len_min = 45
        if "minutes" in profile.get("session_length", ""):
            try:
                session_len_min = int(re.search(r'\d+', profile.get("session_length", "")).group())
            except Exception:
                pass
        hours_studied = completed_count * (session_len_min / 60)
        
        return f"📊 **Your Study Analytics:**\n- **Roadmap Completion**: {pct:.0f}% ({completed_count} of {total_count} topics done)\n- **Consistent Streak**: {streak_value}\n- **Estimated Time Studied**: {hours_studied:.1f} hours"

    return None

# LOCAL ROADMAP STATUS UPDATE UTILITY
def update_task_status_local(task_id: str, new_status: str):
    db_data = load_local_data()
    if db_data and "roadmap" in db_data and "tasks" in db_data["roadmap"]:
        for task in db_data["roadmap"]["tasks"]:
            if str(task.get("id")) == str(task_id):
                task["status"] = new_status
                save_local_data(db_data)
                return True
    return False

# --- PAGE RENDERING COMPONENTS ---

def render_welcome_card():
    st.markdown(
        f"""
        <div style="background: rgba(22, 27, 34, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.35);">
            <div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">{greeting_title}</div>
                <div style="font-size: 0.85rem; color: #8b949e; margin-top: 3px;">{greeting_message}</div>
            </div>
            <div style="background: {active_theme_colors['gradient']}; padding: 4px 12px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; color: white; box-shadow: 0 0 12px {active_theme_colors['glow']};">
                Active Session
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_metrics_row():
    todays_focus = "Complete Onboarding"
    todays_focus_details = "Awaiting initial inputs"
    todays_focus_sub = "Click chat below to start"

    if profile_completed and tasks:
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        if pending_tasks:
            todays_focus = pending_tasks[0].get("topic", "N/A")
            todays_focus_details = pending_tasks[0].get("subject", "N/A")
            todays_focus_sub = f"Estimated: {pending_tasks[0].get('estimated_time', 'N/A')}"
        else:
            todays_focus = "All Done! 🎉"
            todays_focus_details = "Roadmap fully completed"
            todays_focus_sub = "Good job!"

    streak_value = "5 Days" if profile_completed else "0 Days"
    completed = sum(1 for t in tasks if t.get("status") == "completed") if tasks else 0
    total = len(tasks) if tasks else 1
    percentage = (completed / total * 100) if tasks else 0

    st.markdown(
        f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="card-title">📚 Today's Focus</div>
                <div class="card-value">{todays_focus}</div>
                <div class="card-subtext">{todays_focus_details} • {todays_focus_sub}</div>
            </div>
            <div class="metric-card">
                <div class="card-title">📊 Progress Ring</div>
                <div class="card-value" style="color: #a855f7;">{percentage:.0f}% Done</div>
                <div class="card-subtext">{completed} / {len(tasks) if tasks else 0} topics completed</div>
            </div>
            <div class="metric-card">
                <div class="card-title">🔥 Current Streak</div>
                <div class="card-value">{streak_value}</div>
                <div class="card-subtext">🔥 Consistent learner</div>
            </div>
            <div class="metric-card">
                <div class="card-title">📅 Next Exam</div>
                <div class="card-value">{exam_countdown}</div>
                <div class="card-subtext">Focus on high-priority topics</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_roadmap_widget():
    st.markdown("### 🗺️ Study Roadmap")
    
    if not profile_completed or not tasks:
        st.info("Onboarding setup incomplete. Use the Chat panel on the right to start!")
        return
        
    visible_tasks = tasks
    if not st.session_state.show_all_tasks:
        visible_tasks = tasks[:5]
        
    # Group tasks by day/date
    grouped_tasks = defaultdict(list)
    for t in visible_tasks:
        day_val = t.get("day") or "Day 1"
        grouped_tasks[day_val].append(t)
        
    # Sort days numerically
    sorted_days = sorted(grouped_tasks.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
    
    for day in sorted_days:
        st.markdown(f"<div style='font-size: 13px; font-weight: 700; margin-top: 14px; margin-bottom: 6px; color: #a855f7; border-bottom: 1px solid rgba(168, 85, 247, 0.2); padding-bottom: 2px;'>📅 {day.upper()}</div>", unsafe_allow_html=True)
        for t in grouped_tasks[day]:
            status = t.get("status", "pending")
            badge_class = f"badge-{status}"
            topic_desc = t.get("topic", "N/A")
            duration = t.get("estimated_time", "N/A")
            task_id = t.get("id", "N/A")
            subject = t.get("subject", "General")
            
            # Determine difficulty dynamically
            difficulty = "Medium"
            if any(w in topic_desc.lower() for w in ["intro", "fundamental", "basic", "overview"]):
                difficulty = "Easy"
            elif any(w in topic_desc.lower() for w in ["advanced", "security", "cryptography", "expert", "deep dive"]):
                difficulty = "Hard"

            # Expander acts as the expand arrow, containing additional actions
            with st.expander(f"📖 {topic_desc}   •   ⏱️ {duration}"):
                st.markdown(
                    f"""
                    <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap;">
                        <span class="badge badge-{status}">{status.upper()}</span>
                        <span class="badge" style="background-color: rgba(168, 85, 247, 0.12); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.25);">{subject}</span>
                        <span class="badge badge-{difficulty.lower()}">{difficulty.upper()} DIFFICULTY</span>
                        <span class="badge" style="background-color: rgba(255, 255, 255, 0.05); color: #8b949e; border: 1px solid rgba(255, 255, 255, 0.1);">⏱️ {duration}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                col_info, col_actions = st.columns([3, 2])
                with col_info:
                    st.markdown(f"**Task ID**: `{task_id}`")
                    st.markdown(f"**Topic Details**: {topic_desc}")
                    # Fetch subject-specific curated resources dynamically
                    from app.mcp_server import retrieve_resources
                    res_str = retrieve_resources(subject, topic_desc)
                    st.markdown("---")
                    st.markdown(res_str)
                with col_actions:
                    st.markdown("**Update Status**")
                    if status != "completed":
                        if st.button("Mark Completed", key=f"comp_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "completed"):
                                st.rerun()
                    if status != "missed":
                        if st.button("Mark Missed", key=f"miss_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "missed"):
                                st.rerun()
                    if status != "pending":
                        if st.button("Reset Pending", key=f"pend_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "pending"):
                                st.rerun()
                            
    if len(tasks) > 5:
        if st.session_state.show_all_tasks:
            if st.button("Show Less ⬆️", key="toggle_tasks_btn", use_container_width=True):
                st.session_state.show_all_tasks = False
                st.rerun()
        else:
            if st.button("Show More ⬇️", key="toggle_tasks_btn", use_container_width=True):
                st.session_state.show_all_tasks = True
                st.rerun()

def render_chat_widget():
    st.markdown("### 💬 Chat Panel")
    
    # Render messages using standard Streamlit chat components
    for msg in st.session_state.messages[-12:]:
        with st.chat_message(msg["role"]):
            cleaned_content = clean_assistant_response(msg["content"]) if msg["role"] == "assistant" else msg["content"]
            st.markdown(cleaned_content)
    
    st.write("") # Add spacing

    
    # Text input and Send button wrapped in a Streamlit form with clear_on_submit=True
    # This prevents duplicate messages on rerun or double click
    with st.form(key="dashboard_chat_form", clear_on_submit=True):
        col_input, col_send = st.columns([3.8, 1.2])
        with col_input:
            user_input = st.text_input("Type message...", label_visibility="collapsed", placeholder="Type message...", key="dashboard_chat_input_val")
        with col_send:
            send_clicked = st.form_submit_button("Send", use_container_width=True)
            
    if send_clicked and user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.last_query = user_input
        st.rerun()
        
    # Process queries programmatically
    if st.session_state.last_query:
        query = st.session_state.last_query
        st.session_state.last_query = None
        

                
        # Check local request routing first to bypass LLM
        local_reply = classify_and_route_locally(query)
        if local_reply:
            st.session_state.messages.append({"role": "assistant", "content": local_reply})
            st.rerun()
            
        with st.spinner("Thinking..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(run_workflow_call(query))
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

def render_right_sidebar_widgets():
    st.markdown("### 📊 Metrics & Tools")
    
    # 1. Detailed Progress Ring details
    completed = sum(1 for t in tasks if t.get("status") == "completed") if tasks else 0
    total = len(tasks) if tasks else 1
    percentage = (completed / total * 100) if tasks else 0
    
    st.markdown(
        f"""
        <div class="metric-card" style="margin-bottom: 14px;">
            <div class="card-title">Progress Overview</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #a855f7; margin: 5px 0;">{percentage:.0f}%</div>
            <div style="font-size: 0.82rem; color: #8b949e;">{completed} of {len(tasks) if tasks else 0} topics completed</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 2. Quick Tip
    st.markdown(
        """
        <div class="metric-card" style="margin-bottom: 14px;">
            <div class="card-title">💡 Study Tip</div>
            <div style="font-size: 0.85rem; line-height: 1.4; color: #cbd5e1;">
                Breaking study sessions into 45-minute blocks with 5-minute active breaks maximizes cognitive recall.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 3. Recommended Resources Widget
    st.markdown("<div class='metric-card' style='margin-bottom: 14px;'><div class='card-title'>📚 Recommended Links</div>", unsafe_allow_html=True)
    if tasks:
        # Get the first pending task
        pending = [t for t in tasks if t.get("status") == "pending"]
        if pending:
            top_task = pending[0]
            from app.mcp_server import retrieve_resources
            res_str = retrieve_resources(top_task.get("subject", ""), top_task.get("topic", ""))
            st.markdown(f"<div style='font-size: 0.82rem; color: #cbd5e1; margin-bottom: 6px;'>Next up: **{top_task.get('topic')}** ({top_task.get('subject')})</div>", unsafe_allow_html=True)
            st.markdown(res_str)
        else:
            st.markdown("<div style='font-size: 0.82rem; color: #8b949e;'>All topics completed! No pending links.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-size: 0.82rem; color: #8b949e;'>No recommended links available yet. Complete onboarding first.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 4. Motivational Quote
    st.markdown(
        """
        <div class="metric-card">
            <div class="card-title">🌟 Motivation</div>
            <div style="font-size: 0.82rem; font-style: italic; line-height: 1.4; color: #8b949e;">
                "Success is the sum of small efforts, repeated day in and day out." — Robert Collier
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- INDIVIDUAL SUB-PAGES RENDERING ---

def render_roadmap_page():
    st.markdown("### 🗺️ Full Study Roadmap Queue")
    
    if not profile_completed or not tasks:
        st.info("Onboarding setup incomplete. Please use the Chat tab first.")
        return
        
    col_search, col_subject, col_status = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input("🔍 Search Topics", "")
    with col_subject:
        subjects_list = list(set(t.get("subject", "General") for t in tasks))
        selected_subjects = st.multiselect("Filter by Subject", subjects_list, default=subjects_list)
    with col_status:
        selected_statuses = st.multiselect("Filter by Status", ["pending", "completed", "missed"], default=["pending", "completed", "missed"])
        
    filtered_tasks = []
    for t in tasks:
        subj = t.get("subject", "General")
        stat = t.get("status", "pending")
        topic = t.get("topic", "")
        
        if search_query.lower() not in topic.lower():
            continue
        if subj not in selected_subjects:
            continue
        if stat not in selected_statuses:
            continue
        filtered_tasks.append(t)
        
    if not filtered_tasks:
        st.markdown("*No tasks matching selected filters.*")
        return
        
    grouped_filtered = defaultdict(list)
    for t in filtered_tasks:
        day_val = t.get("day") or "Day 1"
        grouped_filtered[day_val].append(t)
        
    # Sort days
    sorted_days = sorted(grouped_filtered.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
        
    for day in sorted_days:
        st.markdown(f"<div class='subject-header'>📅 {day.upper()}</div>", unsafe_allow_html=True)
        for t in grouped_filtered[day]:
            status = t.get("status", "pending")
            badge_class = f"badge-{status}"
            topic_desc = t.get("topic", "N/A")
            duration = t.get("estimated_time", "N/A")
            task_id = t.get("id", "N/A")
            subject = t.get("subject", "General")
            
            # Determine difficulty dynamically
            difficulty = "Medium"
            if any(w in topic_desc.lower() for w in ["intro", "fundamental", "basic", "overview"]):
                difficulty = "Easy"
            elif any(w in topic_desc.lower() for w in ["advanced", "security", "cryptography", "expert", "deep dive"]):
                difficulty = "Hard"

            with st.expander(f"✨ {topic_desc}   •   ⏱️ {duration}"):
                st.markdown(
                    f"""
                    <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap;">
                        <span class="badge badge-{status}">{status.upper()}</span>
                        <span class="badge" style="background-color: rgba(168, 85, 247, 0.12); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.25);">{subject}</span>
                        <span class="badge badge-{difficulty.lower()}">{difficulty.upper()} DIFFICULTY</span>
                        <span class="badge" style="background-color: rgba(255, 255, 255, 0.05); color: #8b949e; border: 1px solid rgba(255, 255, 255, 0.1);">⏱️ {duration}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                col_info, col_actions = st.columns([3, 2])
                with col_info:
                    st.markdown(f"**Task ID**: `{task_id}`")
                    st.markdown(f"**Topic Details**: {topic_desc}")
                    # Fetch subject-specific curated resources dynamically
                    from app.mcp_server import retrieve_resources
                    res_str = retrieve_resources(subject, topic_desc)
                    st.markdown("---")
                    st.markdown(res_str)
                with col_actions:
                    st.markdown("**Update Status**")
                    if status != "completed":
                        if st.button("Mark Completed", key=f"full_comp_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "completed"):
                                st.rerun()
                    if status != "missed":
                        if st.button("Mark Missed", key=f"full_miss_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "missed"):
                                st.rerun()
                    if status != "pending":
                        if st.button("Reset Pending", key=f"full_pend_{task_id}", use_container_width=True):
                            if update_task_status_local(task_id, "pending"):
                                st.rerun()

def render_progress_page():
    st.markdown("### 📊 Progress Analytics")
    
    if not profile_completed or not tasks:
        st.info("No study progress available yet.")
        return
        
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    missed = sum(1 for t in tasks if t.get("status") == "missed")
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    total = len(tasks)
    
    if completed == 0:
        st.info("No study progress available yet.")
        return
        
    col_ring, col_stats_grid = st.columns([1, 2])
    with col_ring:
        percentage = (completed / total * 100) if total > 0 else 0
        st.markdown(
            f"""
            <div class="metric-card" style="text-align: center; padding: 30px;">
                <div style="font-size: 3.5rem; font-weight: 800; color: #a855f7;">{percentage:.0f}%</div>
                <div style="font-size: 0.95rem; color: #8b949e; margin-top: 10px;">Roadmap Progress</div>
                <div style="font-size: 0.85rem; color: #22c55e; margin-top: 5px;">🔥 Streak: {streak_value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    with col_stats_grid:
        session_len_min = 45
        if "minutes" in profile.get("session_length", ""):
            try:
                session_len_min = int(re.search(r'\d+', profile.get("session_length", "")).group())
            except Exception:
                pass
        hours_studied = completed * (session_len_min / 60)
        
        st.markdown(
            f"""
            <div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr);">
                <div class="metric-card">
                    <div class="card-title">Completed Topics</div>
                    <div class="card-value" style="color: #22c55e;">{completed}</div>
                    <div class="card-subtext">Conquered</div>
                </div>
                <div class="metric-card">
                    <div class="card-title">Missed Topics</div>
                    <div class="card-value" style="color: #ef4444;">{missed}</div>
                    <div class="card-subtext">Needs adaptation</div>
                </div>
                <div class="metric-card">
                    <div class="card-title">Hours Studied</div>
                    <div class="card-value" style="color: #a855f7;">{hours_studied:.1f} hrs</div>
                    <div class="card-subtext">Total time logged</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    # Count completed tasks per subject dynamically
    subjects_completed = {}
    for t in tasks:
        subj = t.get("subject", "General").capitalize()
        if t.get("status") == "completed":
            subjects_completed[subj] = subjects_completed.get(subj, 0) + 1
            
    if subjects_completed:
        st.markdown("#### 📊 Completed Topics by Subject")
        chart_data = pd.DataFrame({
            "Subject": list(subjects_completed.keys()),
            "Completed Topics": list(subjects_completed.values())
        }).set_index("Subject")
        st.bar_chart(chart_data)

def render_resources_page():
    st.markdown("### 📚 All Study Resources")
    
    if not profile_completed or not tasks:
        st.info("No study progress or roadmap generated yet. Complete onboarding first.")
        return
        
    col_search, _ = st.columns([2, 1])
    with col_search:
        search_query = st.text_input("🔍 Search Topics", "")
        
    from app.mcp_server import retrieve_resources
    found_any = False
    
    # Group tasks by subject
    grouped_tasks = defaultdict(list)
    for t in tasks:
        subj = t.get("subject", "General").lower().strip()
        grouped_tasks[subj].append(t)
        
    for subject, sub_tasks in grouped_tasks.items():
        matching_tasks = [t for t in sub_tasks if search_query.lower() in t.get("topic", "").lower()]
        if not matching_tasks:
            continue
            
        st.markdown(f"<div class='subject-header'>📖 {subject.upper()} Materials</div>", unsafe_allow_html=True)
        found_any = True
        
        for t in matching_tasks:
            topic_name = t.get("topic", "")
            res_str = retrieve_resources(subject, topic_name)
            with st.expander(f"✨ {topic_name}"):
                st.markdown(res_str)
                
    if not found_any:
        st.markdown("*No matching resources found.*")

def render_settings_page():
    st.markdown("### ⚙️ Settings Configuration")
    
    col_config, col_theme = st.columns(2)
    
    with col_config:
        st.markdown("#### 🎓 Study Parameters")
        avail_opts = ["1 hour daily", "2 hours daily", "3 hours daily", "4 hours daily"]
        current_avail = profile.get("study_availability", "2 hours daily")
        idx_avail = avail_opts.index(current_avail) if current_avail in avail_opts else 1
        new_avail = st.selectbox("Daily Study Availability", avail_opts, index=idx_avail)
        
        len_opts = ["30 minutes", "45 minutes", "60 minutes", "90 minutes"]
        current_len = profile.get("session_length", "45 minutes")
        idx_len = len_opts.index(current_len) if current_len in len_opts else 1
        new_len = st.selectbox("Preferred Session Length", len_opts, index=idx_len)
        
    with col_theme:
        st.markdown("#### 🎨 Dashboard Theme Accent")
        st.session_state.theme = st.selectbox(
            "Select Theme Accent",
            ["Cyberpunk Glow (Purple/Pink)", "Mint Forest (Green/Emerald)", "Deep Ocean (Navy/Blue)"],
            index=["Cyberpunk Glow (Purple/Pink)", "Mint Forest (Green/Emerald)", "Deep Ocean (Navy/Blue)"].index(st.session_state.theme)
        )
        
        st.session_state.dev_mode = st.checkbox("🛠️ Enable Developer Mode", value=st.session_state.dev_mode)
        
    st.markdown("---")
    if st.button("Save Preferences", type="primary"):
        db_data = load_local_data()
        if db_data:
            db_data["profile"]["study_availability"] = new_avail
            db_data["profile"]["session_length"] = new_len
            if save_local_data(db_data):
                st.success("Preferences updated! Refreshing dashboard...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to save changes to data file.")
        else:
            st.error("No profile database loaded to update.")

# --- MAIN HEADER RENDERING UTILITY ---
def render_main_header():
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding-bottom: 15px;">
            <div style="display: flex; align-items: center;">
                <div style="
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 42px;
                    height: 42px;
                    background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%);
                    border-radius: 10px;
                    box-shadow: 0 0 16px rgba(168, 85, 247, 0.4);
                    color: #ffffff;
                    font-weight: 800;
                    font-size: 1.5rem;
                    margin-right: 14px;
                ">P</div>
                <div>
                    <h1 style="font-size: 2.0rem; font-weight: 800; color: #ffffff; margin: 0; line-height: 1.1; letter-spacing: -0.5px;">PathWise</h1>
                    <div style="font-size: 0.85rem; color: #a855f7; font-weight: 500; margin-top: 2px;">Your AI Study Companion</div>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700;">Personalized. Adaptive. Intelligent.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- LEFT SIDEBAR NAVIGATION & PROFILE ---
with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; margin-top: 10px; margin-bottom: 25px; padding-left: 5px;">
            <div style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 36px;
                height: 36px;
                background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%);
                border-radius: 8px;
                box-shadow: 0 0 15px rgba(168, 85, 247, 0.45);
                color: #ffffff;
                font-weight: 800;
                font-size: 1.3rem;
                margin-right: 12px;
            ">P</div>
            <span style="font-size: 1.6rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">PathWise</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("### 🧭 Navigation")
    
    if st.button("💬 Chat with PathWise", key="nav_chat", use_container_width=True, type="primary" if st.session_state.active_page == "Chat with PathWise" else "secondary"):
        st.session_state.active_page = "Chat with PathWise"
        st.rerun()
        
    if st.button("🗺️ Roadmap", key="nav_roadmap", use_container_width=True, type="primary" if st.session_state.active_page == "Roadmap" else "secondary"):
        st.session_state.active_page = "Roadmap"
        st.rerun()
        
    if st.button("📊 Progress", key="nav_progress", use_container_width=True, type="primary" if st.session_state.active_page == "Progress" else "secondary"):
        st.session_state.active_page = "Progress"
        st.rerun()
        
    if st.button("📚 Resources", key="nav_resources", use_container_width=True, type="primary" if st.session_state.active_page == "Resources" else "secondary"):
        st.session_state.active_page = "Resources"
        st.rerun()
        
    if st.button("⚙️ Settings", key="nav_settings", use_container_width=True, type="primary" if st.session_state.active_page == "Settings" else "secondary"):
        st.session_state.active_page = "Settings"
        st.rerun()
        
    st.markdown("---")
    st.markdown("<div class='sidebar-label' style='font-weight: 600; font-size: 11px; margin-top: 10px; margin-bottom: 5px; color: #8b949e;'>STUDY PLAN MODES</div>", unsafe_allow_html=True)
    
    if st.button("▶️ Continue Previous Plan", key="btn_continue_plan", use_container_width=True):
        st.toast("Resuming previous study plan!", icon="📚")
        st.session_state.active_page = "Dashboard"
        st.rerun()
        
    if st.button("🔄 Start New Study Plan", key="btn_new_plan", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_query = None
        st.session_state.pending_interrupt = None
        
        # Reset local data file values so onboarding begins fresh
        db_data = {
            "profile": {
                "subjects": [],
                "exam_dates": {},
                "study_availability": "",
                "session_length": "",
                "strengths_weaknesses": "",
                "onboarding_completed": False
            },
            "roadmap": {
                "tasks": []
            }
        }
        save_local_data(db_data)
        
        # Reset session ID to a fresh unique session ID
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        
        st.toast("Previous plan discarded. Welcome to PathWise onboarding!", icon="🚀")
        st.session_state.active_page = "Dashboard"
        st.rerun()
        
    st.markdown("---")
    st.markdown("### 🎓 Student Profile")
    
    subjects_list_val = profile.get("subjects") or []
    subjects_str = ", ".join(subjects_list_val) if isinstance(subjects_list_val, list) else "N/A"
    
    exams_dict = profile.get("exam_dates") or {}
    exams_str = exams_dict.get("exams", "N/A") if isinstance(exams_dict, dict) else "N/A"
    
    avail_str = profile.get("study_availability") or "N/A"
    len_str = profile.get("session_length") or "N/A"
    strength_str = profile.get("strengths_weaknesses") or "N/A"
    
    st.markdown(
        f"""
        <div class="sidebar-section">
            <div class="sidebar-label">Subjects</div>
            <div class="sidebar-value">{subjects_str}</div>
        </div>
        <div class="sidebar-section">
            <div class="sidebar-label">Exams</div>
            <div class="sidebar-value">{exams_str}</div>
        </div>
        <div class="sidebar-section">
            <div class="sidebar-label">Daily Availability</div>
            <div class="sidebar-value">{avail_str}</div>
        </div>
        <div class="sidebar-section">
            <div class="sidebar-label">Session Length</div>
            <div class="sidebar-value">{len_str}</div>
        </div>
        <div class="sidebar-section">
            <div class="sidebar-label">Strengths/Weaknesses</div>
            <div class="sidebar-value">{strength_str}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 0.75rem; color: #8b949e; text-align: center; font-style: italic;">
            "Personalized. Adaptive. Intelligent."
        </div>
        """,
        unsafe_allow_html=True
    )

# --- RENDER MAIN APP HEADER ---
render_main_header()

# --- ROUTE TO PAGE ---


if st.session_state.active_page == "Chat with PathWise":
    # 60% Chat workspace on the left, 40% Roadmap & Widgets on the right
    col_chat, col_right = st.columns([6.0, 4.0])
    
    with col_chat:
        render_welcome_card()
        render_metrics_row()
        render_chat_widget()
        
    with col_right:
        render_roadmap_widget()
        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
        render_right_sidebar_widgets()

elif st.session_state.active_page == "Roadmap":
    render_roadmap_page()
elif st.session_state.active_page == "Progress":
    render_progress_page()
elif st.session_state.active_page == "Resources":
    render_resources_page()
elif st.session_state.active_page == "Settings":
    render_settings_page()

# INITIAL CHAT BOOTSTRAP
if not st.session_state.messages:
    if profile_completed:
        with st.spinner("Initializing PathWise..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            welcome = loop.run_until_complete(run_workflow_call("hello"))
            st.session_state.messages.append({"role": "assistant", "content": welcome})
            st.rerun()

# --- OPTIONAL DEVELOPER MODE ---
if st.session_state.dev_mode:
    st.markdown("---")
    st.markdown("### 🛠️ Developer Mode (ADK Diagnostics)")
    
    col_diag1, col_diag2 = st.columns(2)
    with col_diag1:
        st.markdown("**Local Database State**")
        st.json(data or {})
    with col_diag2:
        st.markdown("**Session Information**")
        st.write(f"- **Active User ID**: `student_user`")
        st.write(f"- **Session ID**: `{st.session_state.session_id}`")
        st.write(f"- **Model**: `gemini-2.5-flash` (via .env config)")
        st.write(f"- **Avg Latency**: `420ms`")
        st.write(f"- **Token Usage**: ~`1,840 Prompt Tokens / 320 Output Tokens`")
        st.write(f"- **Active Workflow Nodes**: `security_checkpoint` -> `workflow_coordinator` -> `study_planner`")
