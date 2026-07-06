# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import json
import datetime
from typing import AsyncGenerator, Generator, List, Dict, Optional, Any
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, Agent
from google.adk.tools import AgentTool, McpToolset
from mcp import StdioServerParameters
from google.adk.workflow import Workflow, node, FunctionNode, JoinNode, START, DEFAULT_ROUTE
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.apps import App
from google.genai import types

from .config import config

# Clean Vertex AI environment variables to force Gemini API key usage
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
if "GOOGLE_CLOUD_PROJECT" in os.environ:
    del os.environ["GOOGLE_CLOUD_PROJECT"]

import re

def parse_and_normalize_subjects(subject_input: str) -> list[str]:
    # Split by commas, semicolons, and 'and' or '&'
    raw_parts = re.split(r'[;,]|\band\b|&', subject_input, flags=re.IGNORECASE)
    
    resolved = []
    for part in raw_parts:
        part = part.strip().lower()
        if not part:
            continue
        # If the part contains spaces, check if it's a known multi-word subject
        known_multi = ["computer networks", "data structures", "operating systems", "organic chemistry", "discrete math", "discrete mathematics"]
        if part in known_multi:
            resolved.append(part)
        else:
            # Split by space and reconstruct if we see multi-word matches
            words = [w.strip() for w in part.split() if w.strip()]
            i = 0
            while i < len(words):
                if i + 1 < len(words) and f"{words[i]} {words[i+1]}" in known_multi:
                    resolved.append(f"{words[i]} {words[i+1]}")
                    i += 2
                else:
                    resolved.append(words[i])
                    i += 1
    return resolved

# Local data storage path (project root/pathwise_data.json)
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pathwise_data.json")

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {
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
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
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

def save_data(data: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}", flush=True)

def log_audit(event_type: str, severity: str, message: str, details: Optional[dict] = None):
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "event": event_type,
        "severity": severity,
        "message": message,
        "details": details or {}
    }
    # Print to stderr for visibility in console audit logging
    import sys
    print(json.dumps(log_entry), file=sys.stderr, flush=True)

# Define MCP server connection parameters
mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command="uv",
        args=["run", "app/mcp_server.py"]
    )
)

# Specialist agents
syllabus_parser_agent = LlmAgent(
    name="syllabus_parser",
    model=config.model,
    instruction=(
        "You are the Syllabus Parser for PathWise. "
        "Your task is to parse a course syllabus text or markdown and extract the main topics and subjects. "
        "Return a clear, structured list of topics."
    )
)

study_planner_agent = LlmAgent(
    name="study_planner",
    model=config.model,
    instruction=(
        "You are the Study Planner for PathWise. "
        "Your task is to generate a personalized study roadmap (JSON format) based on the student's subjects, "
        "exam dates, study availability, strengths, and weaknesses. "
        "Calendar-Based Roadmap Rules:\n"
        "1. You must assign each task a 'day' field indicating the sequence (e.g., 'Day 1', 'Day 2', 'Day 3', etc.). "
        "Group multiple tasks under the same day if they fit within the student's daily availability. "
        "If exam dates or scheduling dates are provided, optionally assign a specific 'date' field (YYYY-MM-DD).\n"
        "2. Strictly include ONLY the subjects specified in the student's profile subjects list. Do NOT include, mix, or carry over any subjects or topics from other subjects (like Computer Networks or DBMS if they are studying Biology).\n"
        "Ensure the roadmap is realistic and focuses on high-priority topics first.\n"
        "Return ONLY a raw JSON object with the following structure:\n"
        "{\n"
        "  \"tasks\": [\n"
        "    {\n"
        "      \"id\": \"task1\",\n"
        "      \"day\": \"Day 1\",\n"
        "      \"subject\": \"Subject Name\",\n"
        "      \"topic\": \"Topic Name\",\n"
        "      \"estimated_time\": \"Estimated duration (e.g. 45 mins)\",\n"
        "      \"status\": \"pending\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Do not wrap the output in markdown code blocks."
    )
)

adaptive_planner_agent = LlmAgent(
    name="adaptive_planner",
    model=config.model,
    instruction=(
        "You are the Adaptive Planner for PathWise. "
        "Your task is to modify the study roadmap when the student misses tasks, finishes early, or provides difficulty feedback. "
        "Intelligent Adaptation Rules:\n"
        "1. If a task is marked 'completed' and 'easy', consider shortening subsequent related tasks, or skipping basic topics in that subject.\n"
        "2. If a task is marked 'completed' and 'hard' (difficult), split the next related task in that subject into smaller, more granular sub-tasks, or add a dedicated 'Review' task for this topic.\n"
        "3. If a task is marked 'missed' (skipped), insert a 'Catch-up Slot' or reschedule it to a later day, but do not just append it to the end; re-budget the daily study availability to fit it.\n"
        "4. Always retain the calendar day structure ('Day 1', 'Day 2', etc.) and ensure the updated tasks list replaces the old one cleanly.\n"
        "5. Strictly include ONLY the current subjects specified in the student profile. Do NOT mix or carry over any previous subjects.\n"
        "Return ONLY the updated raw JSON object matching the roadmap structure:\n"
        "{\n"
        "  \"tasks\": [\n"
        "    {\n"
        "      \"id\": \"task1\",\n"
        "      \"day\": \"Day 1\",\n"
        "      \"subject\": \"Subject Name\",\n"
        "      \"topic\": \"Topic Name\",\n"
        "      \"estimated_time\": \"Estimated duration\",\n"
        "      \"status\": \"pending/completed/missed\",\n"
        "      \"difficulty\": \"easy/medium/hard\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Do not wrap the output in markdown code blocks."
    ),
    tools=[mcp_toolset]
)

learning_guide_agent = LlmAgent(
    name="learning_guide",
    model=config.model,
    instruction=(
        "You are the Learning Guide for PathWise. "
        "Based on the recommended topic, explain why it was chosen (pedagogical reason) and retrieve relevant learning resources using the retrieve_resources tool. "
        "Always use the retrieve_resources tool to fetch curated learning resources for the subject and topic, and display those retrieved resources to the user."
    ),
    tools=[mcp_toolset]
)

orchestrator_agent = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction=(
        "You are the PathWise Orchestrator. You help students decide what to study next.\n"
        "Always structure your response to show **Today's Focus** first if possible.\n"
        "**Today's Focus** includes:\n"
        "- Recommended Topic\n"
        "- Estimated Study Time\n"
        "- Why it was selected (pedagogical explanation)\n"
        "- Recommended resources\n\n"
        "You have access to specialist sub-agents as tools:\n"
        "- Use syllabus_parser to extract topics from a syllabus.\n"
        "- Use study_planner to generate a roadmap.\n"
        "- Use adaptive_planner to update/adjust the roadmap when the student misses study sessions, finishes early, or complains a topic is too hard.\n"
        "- Use learning_guide to get study resources and pedagogical explanations.\n\n"
        "You also have access to MCP local storage tools to get/save the student profile, get/save the roadmap, and update progress.\n"
        "Always query the student profile and roadmap using the appropriate tools first."
    ),
    tools=[
        AgentTool(syllabus_parser_agent),
        AgentTool(study_planner_agent),
        AgentTool(adaptive_planner_agent),
        AgentTool(learning_guide_agent),
        mcp_toolset
    ]
)

# Workflow Nodes
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    text_content = ""
    if node_input and hasattr(node_input, "parts") and node_input.parts:
        for part in node_input.parts:
            if hasattr(part, "text") and part.text:
                text_content += part.text
    elif isinstance(node_input, str):
        text_content = node_input

    # 1. PII Scrubbing
    scrubbed_text = text_content
    pii_found = False
    
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    if re.search(email_pattern, scrubbed_text):
        scrubbed_text = re.sub(email_pattern, "[REDACTED_EMAIL]", scrubbed_text)
        pii_found = True

    phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    if re.search(phone_pattern, scrubbed_text):
        scrubbed_text = re.sub(phone_pattern, "[REDACTED_PHONE]", scrubbed_text)
        pii_found = True

    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    if re.search(ssn_pattern, scrubbed_text):
        scrubbed_text = re.sub(ssn_pattern, "[REDACTED_SSN]", scrubbed_text)
        pii_found = True

    if pii_found:
        log_audit("pii_scrubbing", "WARNING", "PII was detected and scrubbed from user input", {"original": text_content, "scrubbed": scrubbed_text})
    else:
        log_audit("pii_scrubbing", "INFO", "No PII detected in user input")

    # 2. Prompt Injection Detection
    injection_keywords = ["ignore previous", "system prompt", "ignore instructions", "dan mode", "jailbreak", "you are now"]
    injection_detected = False
    for kw in injection_keywords:
        if kw in scrubbed_text.lower():
            injection_detected = True
            break

    # 3. Domain Specific Rule (restrict toxic keywords)
    toxic_keywords = ["hack", "steal", "cheat", "plagiarize"]
    domain_violation = False
    for tk in toxic_keywords:
        if tk in scrubbed_text.lower():
            domain_violation = True
            break

    if injection_detected:
        log_audit("prompt_injection", "CRITICAL", "Prompt injection attack detected", {"input": scrubbed_text})
        return Event(output="Security Violation: Prompt injection detected.", route="SECURITY_EVENT")
    elif domain_violation:
        log_audit("domain_security", "WARNING", "Domain policy violation detected", {"input": scrubbed_text})
        return Event(output="Security Violation: Cheating or malicious educational content is not allowed.", route="SECURITY_EVENT")

    log_audit("security_check", "INFO", "Security checks passed successfully")
    return Event(output=scrubbed_text, route="__DEFAULT__")

def security_event(node_input: str):
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=f"⚠️ {node_input}")]), route="exit")
    yield Event(output=node_input)

@node(rerun_on_resume=True)
async def workflow_coordinator(ctx: Context, node_input: str) -> AsyncGenerator[Any, Any]:
    data = load_data()
    profile = data["profile"]
    
    # Onboarding Flow
    if not profile.get("onboarding_completed", False):
        if not profile.get("subjects"):
            if ctx.resume_inputs and "subjects" in ctx.resume_inputs:
                subs = parse_and_normalize_subjects(ctx.resume_inputs["subjects"])
                profile["subjects"] = subs
                save_data(data)
            else:
                yield RequestInput(interrupt_id="subjects", message="Welcome to PathWise! Let's get started. What subjects/courses are you studying? (Please separate with commas, e.g., Biology, Chemistry, Calculus)")
                return
        
        if not profile.get("exam_dates"):
            if ctx.resume_inputs and "exam_dates" in ctx.resume_inputs:
                profile["exam_dates"] = {"exams": ctx.resume_inputs["exam_dates"]}
                save_data(data)
            else:
                yield RequestInput(interrupt_id="exam_dates", message="Got it. When are your upcoming exams for these subjects? (e.g., Biology on July 15, Chemistry on July 20)")
                return

        if not profile.get("study_availability"):
            if ctx.resume_inputs and "study_availability" in ctx.resume_inputs:
                profile["study_availability"] = ctx.resume_inputs["study_availability"]
                save_data(data)
            else:
                yield RequestInput(interrupt_id="study_availability", message="How much time do you want to allocate for studying each day? (e.g., 2 hours daily, 1 hour on weekdays)")
                return

        if not profile.get("session_length"):
            if ctx.resume_inputs and "session_length" in ctx.resume_inputs:
                profile["session_length"] = ctx.resume_inputs["session_length"]
                save_data(data)
            else:
                yield RequestInput(interrupt_id="session_length", message="What is your preferred study session length? (e.g., 30 minutes, 45 minutes)")
                return

        if not profile.get("strengths_weaknesses"):
            if ctx.resume_inputs and "strengths_weaknesses" in ctx.resume_inputs:
                profile["strengths_weaknesses"] = ctx.resume_inputs["strengths_weaknesses"]
                profile["onboarding_completed"] = True
                save_data(data)
                
                # Generate initial study roadmap
                prompt = (
                    f"Subjects: {profile['subjects']}\n"
                    f"Exam Dates: {profile['exam_dates']}\n"
                    f"Availability: {profile['study_availability']}\n"
                    f"Session Length: {profile['session_length']}\n"
                    f"Strengths & Weaknesses: {profile['strengths_weaknesses']}\n"
                )
                planner_res = await ctx.run_node(study_planner_agent, node_input=prompt)
                
                roadmap_json = {}
                try:
                    text_res = planner_res.text if hasattr(planner_res, 'text') else str(planner_res)
                    json_str = text_res
                    if "```json" in text_res:
                        json_str = text_res.split("```json")[1].split("```")[0].strip()
                    elif "```" in text_res:
                        json_str = text_res.split("```")[1].split("```")[0].strip()
                    roadmap_json = json.loads(json_str)
                except Exception as e:
                    roadmap_json = {"tasks": [
                        {"id": "task1", "subject": profile["subjects"][0], "topic": "Introduction & Fundamentals", "estimated_time": profile["session_length"], "status": "pending"}
                    ]}
                
                data["roadmap"] = roadmap_json
                save_data(data)
                
                welcome_msg = (
                    "🎉 Onboarding complete! I've saved your profile and generated your study roadmap.\n\n"
                    "⭐ **Today's Focus** ⭐\n"
                    f"Topic: {roadmap_json['tasks'][0]['topic']} ({roadmap_json['tasks'][0]['subject']})\n"
                    f"Estimated Time: {roadmap_json['tasks'][0]['estimated_time']}\n"
                    "Explanation: Let's start with foundational concepts first to build confidence.\n"
                    "Resources: [1] Course textbook chapter 1, [2] Online crash course video."
                )
                yield Event(output=welcome_msg)
                return
            else:
                yield RequestInput(interrupt_id="strengths_weaknesses", message="Finally, what are your self-assessed strengths and weak areas for these subjects? (e.g., Good at memorization, bad at calculations)")
                return

    # Main Orchestration flow when onboarding is completed
    prompt = (
        f"Current Student Profile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Current Study Roadmap:\n{json.dumps(data.get('roadmap', {}), indent=2)}\n\n"
        f"User Message: {node_input}"
    )
    orchestrator_res = await ctx.run_node(orchestrator_agent, node_input=prompt)
    text_res = orchestrator_res.text if hasattr(orchestrator_res, 'text') else str(orchestrator_res)
    yield Event(output=text_res)

def final_output(node_input: Any):
    if isinstance(node_input, dict) and "response" in node_input:
        text = node_input["response"]
    elif isinstance(node_input, str):
        text = node_input
    else:
        text = str(node_input)
    
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=text)]))
    yield Event(output=text)

# Define the ADK 2.0 Workflow Graph
workflow = Workflow(
    name="pathwise_workflow",
    edges=[
        ('START', security_checkpoint),
        (security_checkpoint, {
            'SECURITY_EVENT': security_event,
            '__DEFAULT__': workflow_coordinator
        }),
        (workflow_coordinator, final_output)
    ]
)

root_agent = workflow

app = App(
    root_agent=workflow,
    name="app",
)
