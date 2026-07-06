import os
import json
from typing import List, Dict, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PathWise Local Storage Server")

# Local database file path
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pathwise_data.json")

import re

def parse_and_normalize_subjects(subject_input: str) -> List[str]:
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
    
    # Normalize and clean incoming subjects
    normalized_subjects = []
    for s in subjects:
        normalized_subjects.extend(parse_and_normalize_subjects(s))
    
    # Deduplicate while preserving order
    seen = set()
    unique_subjects = [x for x in normalized_subjects if not (x in seen or seen.add(x))]
    
    data["profile"] = {
        "subjects": unique_subjects,
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
    import sys
    print(f"DEBUG retrieve_resources tool called with subject='{subject}', topic='{topic}'", file=sys.stderr, flush=True)
    # Simulated local database of curated resource links
    resources_db = {
        "biology": {
            "genetics": {
                "textbooks": "[Campbell Biology (12th Edition)](https://www.pearson.com/) - Chapter 14: Mendelian Genetics",
                "youtube_playlists": "[CrashCourse Biology: Heredity & Genetics](https://www.youtube.com/playlist?list=PL3EED4C1D684D3ADF) on YouTube",
                "documentation": "[NIH NCBI Genetics Home Reference Guide](https://medlineplus.gov/genetics/)",
                "practice_websites": "[Khan Academy Genetics Practice](https://www.khanacademy.org/science/ap-biology/heredity/mendelian-genetics/e/mendelian-genetics-questions)",
                "revision_resources": "[AP Biology Genetics Revision Guide](https://apcentral.collegeboard.org/)"
            },
            "botany": {
                "textbooks": "[Campbell Biology (12th Edition)](https://www.pearson.com/) - Chapter 35: Plant Structure & Growth",
                "youtube_playlists": "[Bozeman Science Plant Nutrition](https://www.youtube.com/watch?v=kYJv9O-Msw8) on YouTube",
                "documentation": "[USDA Plant Database & Guides](https://plants.usda.gov/)",
                "practice_websites": "[biologycorner.com Plant Structure Diagrams](https://www.biologycorner.com/)",
                "revision_resources": "[Quizlet Botany Flashcards](https://quizlet.com/)"
            },
            "general": {
                "textbooks": "[Campbell Biology by Lisa A. Urry](https://www.pearson.com/)",
                "youtube_playlists": "[CrashCourse Biology Playlist](https://www.youtube.com/playlist?list=PL3EED4C1D684D3ADF) on YouTube",
                "documentation": "[National Center for Biotechnology Information (NCBI)](https://www.ncbi.nlm.nih.gov/)",
                "practice_websites": "[Khan Academy Biology Practice Exercises](https://www.khanacademy.org/science/biology)",
                "revision_resources": "[AP Biology Crash Course Revision Guide](https://apcentral.collegeboard.org/)"
            }
        },
        "chemistry": {
            "stoichiometry": {
                "textbooks": "[Zumdahl Chemistry](https://www.cengage.com/) - Chapter 3: Chemical Calculations",
                "youtube_playlists": "[Tyler DeWitt's Stoichiometry Playlist](https://www.youtube.com/playlist?list=PL3hPm0ZdYhyx2WnN9-P9P7gWpZ8y0Sj-U) on YouTube",
                "documentation": "[IUPAC Gold Book Mole Definitions](https://goldbook.iupac.org/)",
                "practice_websites": "[ChemQuiz.net Stoichiometry Practice](https://chemquiz.net/sto/)",
                "revision_resources": "[LibreTexts Chemistry Stoichiometry Reference Card](https://chem.libretexts.org/)"
            },
            "thermodynamics": {
                "textbooks": "[Zumdahl Chemistry](https://www.cengage.com/) - Chapter 6: Thermochemistry",
                "youtube_playlists": "[Organic Chemistry Tutor Gibbs Free Energy](https://www.youtube.com/watch?v=8N1BxHg8WZk) on YouTube",
                "documentation": "[NIST Chemistry WebBook Thermodynamic Tables](https://webbook.nist.gov/chemistry/)",
                "practice_websites": "[ChemCollective Virtual Labs & Practice](http://chemcollective.org/)",
                "revision_resources": "[LibreTexts Laws of Thermodynamics Summary](https://chem.libretexts.org/)"
            },
            "general": {
                "textbooks": "[Chemistry by Steven S. Zumdahl](https://www.cengage.com/)",
                "youtube_playlists": "[The Organic Chemistry Tutor General Chemistry](https://www.youtube.com/playlist?list=PL0o_zARPakbKx7Fp84MshS9Gk8fCgscfG)",
                "documentation": "[PubChem Chemical Database](https://pubchem.ncbi.nlm.nih.gov/)",
                "practice_websites": "[ChemQuiz.net Chemistry Practice Problems](https://chemquiz.net/)",
                "revision_resources": "[Compound Interest Chemistry Infographics](https://www.compoundchem.com/)"
            }
        },
        "physics": {
            "kinematics": {
                "textbooks": "[Fundamentals of Physics by Halliday & Resnick](https://www.wiley.com/) - Chapter 2: Motion in 1D",
                "youtube_playlists": "[CrashCourse Physics Kinematics & Motion](https://www.youtube.com/playlist?list=PL8dPuuaLjXtN0ge7yDk_UA0LDN11wU5eV) on YouTube",
                "documentation": "[PhET Interactive Physics Simulation (Motion)](https://phet.colorado.edu/en/simulations/filter?subjects=physics&type=html)",
                "practice_websites": "[Physics Classroom Concept Builders (Kinematics)](https://www.physicsclassroom.com/Concept-Builders/Kinematics)",
                "revision_resources": "[Physics Hypertextbook Kinematics Guide](https://physics.info/kinematics/)"
            },
            "optics": {
                "textbooks": "[Fundamentals of Physics by Halliday & Resnick](https://www.wiley.com/) - Chapter 34-36: Geometrical & Wave Optics",
                "youtube_playlists": "[Walter Lewin Lectures on Light & Optics](https://www.youtube.com/playlist?list=PLyQSN7X0RO33uX5GvGPZCQZp1B0U8_n71) on YouTube",
                "documentation": "[PhET Geometric Optics Simulation](https://phet.colorado.edu/en/simulations/geometric-optics)",
                "practice_websites": "[Physics Classroom Optics Concept Builders](https://www.physicsclassroom.com/Concept-Builders/Light-and-Color)",
                "revision_resources": "[Optics Formulas and Cheat Sheet](https://physics.info/refraction/)"
            },
            "waves": {
                "textbooks": "[Fundamentals of Physics by Halliday & Resnick](https://www.wiley.com/) - Chapter 15-16: Oscillations & Waves",
                "youtube_playlists": "[CrashCourse Physics Oscillations & Sound Waves](https://www.youtube.com/watch?v=tMSgPPzP4Xc) on YouTube",
                "documentation": "[PhET Wave Interference Simulation](https://phet.colorado.edu/en/simulations/wave-interference)",
                "practice_websites": "[Khan Academy Physics Sound & Wave Practice](https://www.khanacademy.org/science/physics/mechanical-waves-and-sound)",
                "revision_resources": "[Waves Behavior & Formula Summary Sheet](https://physics.info/waves/)"
            },
            "general": {
                "textbooks": "[Fundamentals of Physics by Halliday, Resnick, and Walker](https://www.wiley.com/)",
                "youtube_playlists": "[CrashCourse Physics Lecture Series](https://www.youtube.com/playlist?list=PL8dPuuaLjXtN0ge7yDk_UA0LDN11wU5eV)",
                "documentation": "[PhET Interactive Physics Simulations](https://phet.colorado.edu/)",
                "practice_websites": "[Physics Classroom Concept Builders](https://www.physicsclassroom.com/)",
                "revision_resources": "[Physics Hypertextbook Resource Guides](https://physics.info/)"
            }
        },
        "computer networks": {
            "osi model": {
                "textbooks": "[Computer Networks by Andrew S. Tanenbaum](https://www.pearson.com/) - Chapter 1: Reference Models",
                "youtube_playlists": "[Neso Academy OSI Model Explanation](https://www.youtube.com/watch?v=vv4y_uOneC0) on YouTube",
                "documentation": "[RFC 1122 (Internet Standard Protocol Suite)](https://datatracker.ietf.org/doc/html/rfc1122)",
                "practice_websites": "[GeeksforGeeks OSI Layer Quiz Questions](https://www.geeksforgeeks.org/layers-of-osi-model/)",
                "revision_resources": "[cheat-sheets.org OSI Layer Cheat Sheet](https://cheat-sheets.org/)"
            },
            "network layer": {
                "textbooks": "[Computer Networks by Andrew S. Tanenbaum](https://www.pearson.com/) - Chapter 5: Network Layer",
                "youtube_playlists": "[Neso Academy IP Addressing & Subnetting](https://www.youtube.com/playlist?list=PLBlnK6fEyqRgMCUAG0XRw78UA8qnv6jEx) on YouTube",
                "documentation": "[IANA IP Addressing Allocation records](https://www.iana.org/)",
                "practice_websites": "[subnettingquestions.com Practice Quiz](http://www.subnettingquestions.com/)",
                "revision_resources": "[Dijkstra's Routing & Subnetting Tables Guide](https://www.geeksforgeeks.org/dijkstras-shortest-path-algorithm-greedy-algo-7/)"
            },
            "general": {
                "textbooks": "[Computer Networks by Andrew S. Tanenbaum](https://www.pearson.com/)",
                "youtube_playlists": "[Neso Academy & Gate Smashers Networks Playlists](https://www.youtube.com/)",
                "documentation": "[RFC Editor (rfc-editor.org)](https://www.rfc-editor.org/)",
                "practice_websites": "[Sanfoundry Computer Networks MCQs](https://www.sanfoundry.com/computer-networks-questions-answers/)",
                "revision_resources": "[Gate Smashers Networks Revision Notes](https://www.gate-smasher.com/)"
            }
        },
        "dbms": {
            "sql": {
                "textbooks": "[Database System Concepts by Silberschatz, Korth](https://www.mheducation.com/) - Chapter 3-4: SQL",
                "youtube_playlists": "[Gate Smashers SQL playlist](https://www.youtube.com/playlist?list=PLxCzCOWd7aiFAN6I81CgLk56Y645-a5Bf) on YouTube",
                "documentation": "[PostgreSQL SQL Command Reference Documentation](https://www.postgresql.org/docs/current/sql.html)",
                "practice_websites": "[LeetCode Database Problems](https://leetcode.com/problemset/database/) & [HackerRank SQL](https://www.hackerrank.com/domains/sql)",
                "revision_resources": "[W3Schools Interactive SQL Reference](https://www.w3schools.com/sql/)"
            },
            "normalization": {
                "textbooks": "[Database System Concepts by Silberschatz, Korth](https://www.mheducation.com/) - Chapter 8: Relational Database Design",
                "youtube_playlists": "[Neso Academy Relational Normalization](https://www.youtube.com/playlist?list=PLBlnK6fEyqRi_FsG-N4MHIb48Q3pQpld5) on YouTube",
                "documentation": "[Relational Database Design Theory Reference](https://www.geeksforgeeks.org/dbms-normalization-1nf-2nf-3nf-bcnf-4nf-5nf/)",
                "practice_websites": "[Normalization Functional Dependency closures on GfG](https://www.geeksforgeeks.org/functional-dependency-and-attribute-closure-in-dbms/)",
                "revision_resources": "[Relational Schema Normalization decomposition notes](https://www.gate-smasher.com/)"
            },
            "general": {
                "textbooks": "[Database System Concepts by Silberschatz, Korth, Sudarshan](https://www.mheducation.com/)",
                "youtube_playlists": "[Gate Smashers DBMS Video Playlist](https://www.youtube.com/playlist?list=PLxCzCOWd7aiFAN6I81CgLk56Y645-a5Bf)",
                "documentation": "[PostgreSQL Reference Documentation](https://www.postgresql.org/docs/)",
                "practice_websites": "[SQLZoo Interactive Database Exercises](https://sqlzoo.net/)",
                "revision_resources": "[GeeksforGeeks DBMS Short Revision Notes](https://www.geeksforgeeks.org/dbms/)"
            }
        }
    }
    
    sub_key = subject.lower().strip()
    top_key = topic.lower().strip()
    
    # Try finding exact matches, otherwise check if a db subject is a substring
    matched_subject = None
    if sub_key in resources_db:
        matched_subject = sub_key
    else:
        for sk in resources_db:
            if sk in sub_key:
                matched_subject = sk
                break
                
    if matched_subject:
        matched_dict = None
        for k in resources_db[matched_subject]:
            if k in top_key or top_key in k:
                matched_dict = resources_db[matched_subject][k]
                break
        if not matched_dict:
            matched_dict = resources_db[matched_subject]["general"]
            
        return (
            f"📚 **Textbooks**\n• {matched_dict['textbooks']}\n\n"
            f"🎥 **YouTube Playlists**\n• {matched_dict['youtube_playlists']}\n\n"
            f"🔬 **Documentation**\n• {matched_dict['documentation']}\n\n"
            f"📝 **Practice Websites**\n• {matched_dict['practice_websites']}\n\n"
            f"⚡ **Revision Resources**\n• {matched_dict['revision_resources']}"
        )
        
    return (
        f"📖 Search openstax.org or YouTube for standard learning materials on {subject} ({topic}).\n"
        f"🎥 Look up study guides, practice websites, and revision notes specifically for '{subject} {topic}'."
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
