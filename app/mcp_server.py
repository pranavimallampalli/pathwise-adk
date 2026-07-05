import os
import json
from typing import List, Dict, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PathWise Local Storage Server")

# Local database file path
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@mcp.tool()
def get_student_profile() -> str:
    """Retrieve the student's learning profile including subjects, exam dates, availability, and strengths/weaknesses."""
    data = load_data()
    return json.dumps(data["profile"], indent=2)

@mcp.tool()
def save_student_profile(
    subjects: List[str],
    exam_dates: Dict[str, str],
    study_availability: str,
    session_length: str,
    strengths_weaknesses: str,
    onboarding_completed: bool = True
) -> str:
    """Save or update the student profile details in local storage."""
    data = load_data()
    data["profile"] = {
        "subjects": subjects,
        "exam_dates": exam_dates,
        "study_availability": study_availability,
        "session_length": session_length,
        "strengths_weaknesses": strengths_weaknesses,
        "onboarding_completed": onboarding_completed
    }
    save_data(data)
    return "Profile saved successfully."

@mcp.tool()
def get_roadmap() -> str:
    """Retrieve the current personalized study roadmap (the list of all study tasks and their statuses)."""
    data = load_data()
    return json.dumps(data["roadmap"], indent=2)

@mcp.tool()
def save_roadmap(tasks: List[Dict]) -> str:
    """Save or replace the study roadmap tasks list."""
    data = load_data()
    data["roadmap"] = {"tasks": tasks}
    save_data(data)
    return "Roadmap saved successfully."

@mcp.tool()
def update_progress(task_id: str, status: str, difficulty: Optional[str] = None) -> str:
    """Update the status ('pending', 'completed', 'missed') and optional difficulty rating ('easy', 'medium', 'hard') for a specific study task."""
    data = load_data()
    tasks = data["roadmap"].get("tasks", [])
    updated = False
    
    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = status
            if difficulty:
                task["difficulty"] = difficulty
            updated = True
            break
            
    if updated:
        save_data(data)
        return f"Task {task_id} updated successfully: status={status}, difficulty={difficulty}."
    return f"Task {task_id} not found in current roadmap."

@mcp.tool()
def retrieve_resources(subject: str, topic: str) -> str:
    """Retrieve curated resource recommendations (books, videos, practice problems) for a given subject and topic."""
    # Simulated local database of curated resource links
    resources_db = {
        "biology": {
            "genetics": [
                "📖 Read Campbell Biology, Chapter 14 (Mendelian Genetics)",
                "🎥 Watch CrashCourse Biology: Heredity & Genetics on YouTube",
                "📝 Solve Kahn Academy heredity practice exercises"
            ],
            "botany": [
                "📖 Read Campbell Biology, Chapter 35 (Plant Structure & Growth)",
                "🎥 Watch Bozeman Science Plant Nutrition video",
                "📝 Practice labeling plant tissue structures diagram"
            ]
        },
        "chemistry": {
            "stoichiometry": [
                "📖 Read Zumdahl Chemistry, Chapter 3 (Chemical Calculations)",
                "🎥 Watch Tyler DeWitt's Stoichiometry tutorial series on YouTube",
                "📝 Complete the stoichiometry limiting reactant worksheets"
            ],
            "thermodynamics": [
                "📖 Read Zumdahl Chemistry, Chapter 6 (Thermochemistry)",
                "🎥 Watch Organic Chemistry Tutor Gibbs Free Energy video",
                "📝 Complete practice problems on enthalpy and entropy"
            ]
        }
    }
    
    sub_key = subject.lower().strip()
    top_key = topic.lower().strip()
    
    # Try finding exact matches, otherwise return general suggestions
    if sub_key in resources_db:
        for k in resources_db[sub_key]:
            if k in top_key or top_key in k:
                return "\n".join(resources_db[sub_key][k])
        # Default for the subject
        all_res = []
        for v in resources_db[sub_key].values():
            all_res.extend(v)
        return "\n".join(all_res[:3])
        
    return (
        f"📖 Search openstax.org or Khan Academy for standard courses on {subject} ({topic}).\n"
        f"🎥 Watch YouTube explanations for '{subject} {topic}' (channel suggestions: CrashCourse, Khan Academy).\n"
        f"📝 Look up sample practice questions for '{subject} {topic}'."
    )

@mcp.tool()
def generate_roadmap_summary() -> str:
    """Generate a high-level summary of the student's progress and stats across their roadmap."""
    data = load_data()
    tasks = data["roadmap"].get("tasks", [])
    if not tasks:
        return "No study roadmap generated yet. Complete onboarding first."
        
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    missed = sum(1 for t in tasks if t.get("status") == "missed")
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    
    # Calculate difficulty percentages if any completed tasks had ratings
    difficulties = [t.get("difficulty") for t in tasks if t.get("difficulty")]
    diff_summary = ""
    if difficulties:
        easy = difficulties.count("easy")
        medium = difficulties.count("medium")
        hard = difficulties.count("hard")
        diff_summary = f"\n- Difficulty ratings submitted: Easy: {easy}, Medium: {medium}, Hard: {hard}"
        
    return (
        f"📊 Study Roadmap Summary:\n"
        f"- Total Tasks: {total}\n"
        f"- Completed: {completed} ({completed/total:.1%})\n"
        f"- Missed: {missed} ({missed/total:.1%})\n"
        f"- Pending: {pending} ({pending/total:.1%})"
        f"{diff_summary}"
    )

if __name__ == "__main__":
    mcp.run()
