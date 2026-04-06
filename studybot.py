import os
import json
import re
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, session
from anthropic import Anthropic

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATA_DIR = os.path.join(os.path.dirname(__file__), "studybot_data")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
os.makedirs(DATA_DIR, exist_ok=True)

client = Anthropic()

# In-memory session store (quiz state per session)
sessions = {}

TOPICS = {
    "developers": "Developer Volumes & Selection",
    "lines": "Igora Product Lines",
    "mixing": "Mixing Ratios & Processing",
    "tones": "Tone Codes & Color Theory",
    "grey": "Grey Coverage Rules",
    "vibrance": "Igora Vibrance & Special Techniques",
}

TOPIC_DESCRIPTIONS = {
    "developers": "10vol, 20vol, 30vol, 40vol — when and why",
    "lines": "Royal, Vibrance, Color10, Highlifts, Age Blend, Silver Whites…",
    "mixing": "1:1 vs 1:2, processing times, special ratios",
    "tones": "Reading shade codes, double/triple reflexes, tone modifiers",
    "grey": "Grey % thresholds, resistant grey, coverage techniques",
    "vibrance": "Activator Lotion vs Gel, pastels, demi-permanent rules",
}

SYSTEM_PROMPT = """You are a Schwarzkopf Professional color educator specializing in the Igora Royal color system. You have deep expertise in:

IGORA ROYAL PRODUCT LINES:
- Igora Royal (permanent): Full range, levels 1–10 + Highlifts (10-1,10-2,10-4,10-12,10-19,10-21,10-42,10-46)
- Igora Royal Highlifts: Need 40vol (12%), base 7-8, 1:2 ratio (30ml color:60ml developer). Never on pre-colored hair. Levels go up to 3 stops.
- Igora Royal Absolutes (Age Blend, AB line): 30vol, 1:1, mature hair, softer double-reflex, Pro-Age Complex. Codes: 6-07, 6-460, 6-580, 7-450, 7-560, 7-710, 8-01, 8-07, 8-140, 9-560
- Igora Royal Silver Whites: 10vol ONLY, 1:1, deposit only on white/grey hair. SW: Silver, SW: Grey Lilac, SW: Dove Grey, SW: Slate Grey
- Igora Royal Fashion Lights (FL line): 30vol or 40vol, 1:2 ratio for highlights/lowlights. L-00, L-44, L-77, L-88, L-89
- Igora Vibrance (demi-permanent): Does NOT use Royal developer. Uses Vibrance Activator Lotion (1.9%/6vol) or Activator Gel. Ammonia-free. 5-20 min processing. 0-00 Vibrance: gloss/clear tone.
- Igora Color10: 20vol ONLY, 10-minute processing, 1:1 ratio

DEVELOPER VOLUMES (Igora Royal Oil Developer):
- 10vol (3%): Deposit only, no lift, tone-on-tone, refresh color
- 20vol (6%): Standard, up to 1 level lift, standard grey coverage. Exception: -00 shades always require 30vol.
- 30vol (9%): 1-2 levels lift, high grey coverage (50%+), lightening effect
- 40vol (12%): 2-3 levels lift, aggressive lightening, Highlifts ONLY with 40vol

MIXING RATIOS:
- Standard Royal: 1:1 (e.g., 60ml color + 60ml developer)
- Highlifts: 1:2 (60ml + 120ml)
- Fashion Lights: 1:2
- Silver Whites: 1:1
- Absolutes Age Blend: 1:1
- Vibrance: 1:2 (60ml + 120ml) with Activator Lotion

TONE CODES (Schwarzkopf shade code system = Level-ToneCode):
- 0 = Natural
- 1 = Ash (cool/green-based)
- 2 = Ash (more neutral)
- 3 = Gold
- 4 = Beige
- 5 = Red/Violet
- 6 = Violet/Red
- 7 = Copper/Red
- 8 = Warm/Red-Gold
- 9 = Orange/Red
- Double reflex tones (second digit): intensifies or modifies
- e.g., 7-46 = level 7, tone 4 (beige) + 6 (violet) = beige-violet
- 9.5 series = pastel toners (Vibrance only, pre-lightened hair)
- 12 series = Igora Royal Highlifts only

GREY COVERAGE:
- 0-25% grey → standard formulas, any developer
- 25-50% grey → choose a "coverage" shade, may need 30vol
- 50-75% grey → use grey-coverage shades, 30vol, may need -00 to soften
- 75-100% grey (resistant grey) → use Absolutes line OR mix 50% target shade + 50% grey-coverage shade
- -00 shades (e.g., 6-00, 7-00, 8-00) = pure natural, enhance grey coverage; always use 30vol
- The -0 shades (6-0, 7-0, etc.) = natural with slight warmth, standard coverage
- Resistant grey tip: pre-soften OR use Absolutes Age Blend line

VIBRANCE SPECIAL RULES:
- Uses its own Activator Lotion (standard) or Activator Gel (for highlights/balayage)
- NEVER mix Vibrance with Royal developer
- 9.5-series and 10-series shades in Vibrance = pastel toners (pre-lightened hair only)
- Vibrance exclusive shades: 6-23, 6-78, 7-48, 8-19 (NOT available in Royal)
- 0-00 Vibrance = clear gloss, tone equalizer

PROCESSING TIMES:
- Igora Royal: 35-45 min (standard), Highlifts 45-60 min
- Vibrance: 5-20 min (shorter = less deposit)
- Color10: 10 min flat
- Silver Whites: 20-30 min

You are now in QUIZ MODE. Generate multiple-choice questions and grade answers about Schwarzkopf Igora color systems."""

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            return json.load(f)
    return {
        "total_answered": 0,
        "total_correct": 0,
        "current_streak": 0,
        "best_streak": 0,
        "by_topic": {t: {"answered": 0, "correct": 0} for t in TOPICS},
    }

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def update_stats(topic, grade):
    stats = load_stats()
    stats["total_answered"] += 1
    if grade == "correct":
        stats["total_correct"] += 1
        stats["current_streak"] += 1
        if stats["current_streak"] > stats["best_streak"]:
            stats["best_streak"] = stats["current_streak"]
    else:
        stats["current_streak"] = 0
    if topic in stats["by_topic"]:
        stats["by_topic"][topic]["answered"] += 1
        if grade == "correct":
            stats["by_topic"][topic]["correct"] += 1
    save_stats(stats)

def extract_json(text):
    """Extract first valid JSON object or array from text."""
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find JSON block
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
    # Try to find raw JSON array or object
    match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None

@app.route("/")
def index():
    return render_page()

@app.route("/stats")
def get_stats():
    return jsonify(load_stats())

@app.route("/quiz/start", methods=["POST"])
def quiz_start():
    data = request.get_json()
    topic = data.get("topic")
    if topic not in TOPICS:
        return jsonify({"error": "Invalid topic"}), 400

    prompt = f"""Generate exactly 10 multiple-choice quiz questions about: {TOPICS[topic]}
Topic focus: {TOPIC_DESCRIPTIONS[topic]}

Return ONLY a JSON array with exactly 10 objects. Each object must have:
- "question": string (the question text)
- "options": array of exactly 4 strings (A, B, C, D choices — include the letter prefix like "A) ...")
- "answer": string (the correct option letter: "A", "B", "C", or "D")
- "explanation": string (brief explanation of why the answer is correct)

Make questions practical and specific to Schwarzkopf Igora systems. Vary difficulty.
Return ONLY the JSON array, no other text."""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text
        questions = extract_json(raw)
        if not isinstance(questions, list) or len(questions) == 0:
            return jsonify({"error": "Failed to generate questions"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "topic": topic,
        "questions": questions,
        "current": 0,
        "results": [],
        "created": datetime.now().isoformat(),
    }
    return jsonify({
        "session_id": session_id,
        "topic": topic,
        "topic_label": TOPICS[topic],
        "total": len(questions),
        "question": questions[0],
        "index": 0,
    })

@app.route("/quiz/grade", methods=["POST"])
def quiz_grade():
    data = request.get_json()
    session_id = data.get("session_id")
    user_answer = data.get("answer", "").strip()

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    sess = sessions[session_id]
    idx = sess["current"]
    questions = sess["questions"]
    if idx >= len(questions):
        return jsonify({"error": "Quiz already complete"}), 400

    q = questions[idx]
    correct = q.get("answer", "")
    explanation = q.get("explanation", "")

    # Determine if answer is correct
    user_letter = user_answer[0].upper() if user_answer else ""
    is_correct = user_letter == correct.upper()
    grade = "correct" if is_correct else "wrong"

    # Update stats
    update_stats(sess["topic"], grade)

    # Record result
    sess["results"].append({
        "question": q["question"],
        "user_answer": user_answer,
        "correct_answer": correct,
        "grade": grade,
        "explanation": explanation,
    })
    sess["current"] += 1

    has_next = sess["current"] < len(questions)
    next_question = questions[sess["current"]] if has_next else None

    return jsonify({
        "grade": grade,
        "correct_answer": correct,
        "explanation": explanation,
        "has_next": has_next,
        "next_question": next_question,
        "next_index": sess["current"] if has_next else None,
    })

@app.route("/quiz/summary", methods=["POST"])
def quiz_summary():
    data = request.get_json()
    session_id = data.get("session_id")

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    sess = sessions[session_id]
    results = sess["results"]
    topic = sess["topic"]
    total = len(results)
    correct = sum(1 for r in results if r["grade"] == "correct")
    pct = round((correct / total) * 100) if total > 0 else 0

    # Build breakdown
    breakdown = []
    for i, r in enumerate(results):
        breakdown.append({
            "index": i + 1,
            "question": r["question"],
            "grade": r["grade"],
            "user_answer": r["user_answer"],
            "correct_answer": r["correct_answer"],
            "explanation": r["explanation"],
        })

    # Generate encouraging message
    try:
        prompt = f"A student just scored {correct}/{total} ({pct}%) on a quiz about '{TOPICS[topic]}'. Write 2 sentences: one encouraging line about their performance, and one specific tip about this topic they should review. Be warm and supportive."
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        message = resp.content[0].text.strip()
    except Exception:
        message = f"Great effort! You scored {pct}% — keep practicing to master {TOPICS[topic]}."

    stats = load_stats()

    # Clean up session
    del sessions[session_id]

    return jsonify({
        "topic": topic,
        "topic_label": TOPICS[topic],
        "correct": correct,
        "total": total,
        "pct": pct,
        "message": message,
        "breakdown": breakdown,
        "stats": stats,
    })

def render_page():
    topics_json = json.dumps([
        {"id": k, "label": v, "desc": TOPIC_DESCRIPTIONS[k]}
        for k, v in TOPICS.items()
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Schwarzkopf Study Bot</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --rose: #c9848a;
  --rose-dark: #a86068;
  --rose-light: #f8eced;
  --rose-xl: #fdf5f5;
  --bg: #fafaf8;
  --border: #ede8e3;
  --text: #2c2420;
  --muted: #8c7b76;
  --correct: #4a7c59;
  --correct-bg: #edf7f0;
  --wrong: #a05252;
  --wrong-bg: #fdf0f0;
  --partial: #7a6030;
  --partial-bg: #fdf8ed;
  --radius: 12px;
}}

body {{
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}}

/* Header */
.header {{
  background: white;
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}}
.header h1 {{
  font-family: 'DM Serif Display', serif;
  font-size: 1.4rem;
  color: var(--rose-dark);
}}
.header .subtitle {{
  font-size: 0.78rem;
  color: var(--muted);
  margin-top: 2px;
}}
.stats-bar {{
  display: flex;
  gap: 20px;
  font-size: 0.82rem;
  color: var(--muted);
}}
.stats-bar span b {{
  color: var(--rose-dark);
  font-weight: 600;
}}

/* Screens */
.screen {{ display: none; }}
.screen.active {{ display: block; }}

.page-wrap {{
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 20px 60px;
}}

/* Home */
.home-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 2rem;
  color: var(--rose-dark);
  margin-bottom: 6px;
}}
.home-sub {{
  color: var(--muted);
  font-size: 0.95rem;
  margin-bottom: 32px;
}}

.topic-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 40px;
}}
.topic-card {{
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.1s;
}}
.topic-card:hover {{
  border-color: var(--rose);
  box-shadow: 0 4px 16px rgba(201,132,138,0.15);
  transform: translateY(-2px);
}}
.topic-card.selected {{
  border-color: var(--rose-dark);
  background: var(--rose-xl);
}}
.topic-card h3 {{
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text);
}}
.topic-card p {{
  font-size: 0.78rem;
  color: var(--muted);
  line-height: 1.4;
}}
.topic-score {{
  margin-top: 10px;
  font-size: 0.75rem;
  color: var(--rose-dark);
  font-weight: 500;
}}

.start-btn {{
  display: block;
  width: 100%;
  max-width: 320px;
  margin: 0 auto;
  padding: 14px 24px;
  background: var(--rose);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-family: 'DM Sans', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}}
.start-btn:hover {{ background: var(--rose-dark); transform: translateY(-1px); }}
.start-btn:disabled {{ background: #ccc; cursor: not-allowed; transform: none; }}
.start-loading {{ text-align: center; color: var(--muted); font-size: 0.9rem; margin-top: 12px; }}

/* Quiz */
.quiz-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}}
.quiz-topic-label {{
  font-size: 0.82rem;
  color: var(--muted);
  font-weight: 500;
}}
.quiz-progress {{
  font-size: 0.82rem;
  color: var(--rose-dark);
  font-weight: 600;
}}
.progress-bar {{
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin-bottom: 28px;
  overflow: hidden;
}}
.progress-fill {{
  height: 100%;
  background: var(--rose);
  border-radius: 2px;
  transition: width 0.3s;
}}

.question-card {{
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  margin-bottom: 20px;
}}
.question-num {{
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--rose);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}}
.question-text {{
  font-size: 1.05rem;
  line-height: 1.5;
  font-weight: 500;
  margin-bottom: 24px;
}}

.options-list {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}
.option-btn {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.92rem;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
  width: 100%;
}}
.option-btn:hover:not(:disabled) {{
  border-color: var(--rose);
  background: var(--rose-xl);
}}
.option-btn.selected {{
  border-color: var(--rose-dark);
  background: var(--rose-light);
}}
.option-btn:disabled {{ cursor: not-allowed; }}
.option-btn.correct-opt {{
  border-color: var(--correct);
  background: var(--correct-bg);
  color: var(--correct);
  font-weight: 600;
}}
.option-btn.wrong-opt {{
  border-color: var(--wrong);
  background: var(--wrong-bg);
  color: var(--wrong);
}}
.option-letter {{
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: white;
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
}}

.grade-area {{
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 16px;
  display: none;
}}
.grade-area.show {{ display: block; }}
.grade-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.82rem;
  font-weight: 700;
  margin-bottom: 10px;
}}
.grade-badge.correct {{ background: var(--correct-bg); color: var(--correct); }}
.grade-badge.wrong {{ background: var(--wrong-bg); color: var(--wrong); }}
.grade-explanation {{
  font-size: 0.88rem;
  color: var(--muted);
  line-height: 1.5;
}}

.next-btn {{
  display: block;
  width: 100%;
  padding: 13px 24px;
  background: var(--rose);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}}
.next-btn:hover {{ background: var(--rose-dark); }}

/* Results */
.results-score {{
  text-align: center;
  margin-bottom: 32px;
}}
.score-circle {{
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 6px solid var(--rose);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  background: white;
}}
.score-pct {{
  font-family: 'DM Serif Display', serif;
  font-size: 2.2rem;
  color: var(--rose-dark);
  line-height: 1;
}}
.score-label {{
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 2px;
}}
.results-message {{
  font-size: 0.95rem;
  color: var(--muted);
  line-height: 1.6;
  max-width: 480px;
  margin: 0 auto;
}}

.breakdown-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 1.2rem;
  color: var(--text);
  margin-bottom: 16px;
}}
.breakdown-list {{
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 32px;
}}
.breakdown-item {{
  background: white;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 18px;
  border-left: 4px solid var(--border);
}}
.breakdown-item.correct {{ border-left-color: var(--correct); }}
.breakdown-item.wrong {{ border-left-color: var(--wrong); }}
.breakdown-q {{
  font-size: 0.88rem;
  font-weight: 500;
  margin-bottom: 6px;
}}
.breakdown-detail {{
  font-size: 0.80rem;
  color: var(--muted);
  line-height: 1.4;
}}
.breakdown-detail .ans-label {{
  font-weight: 600;
  color: var(--text);
}}

.results-actions {{
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}}
.action-btn {{
  padding: 12px 24px;
  border-radius: var(--radius);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
}}
.action-btn.primary {{
  background: var(--rose);
  color: white;
}}
.action-btn.primary:hover {{ background: var(--rose-dark); }}
.action-btn.secondary {{
  background: white;
  color: var(--rose-dark);
  border: 1.5px solid var(--rose);
}}
.action-btn.secondary:hover {{ background: var(--rose-xl); }}

@media (max-width: 500px) {{
  .topic-grid {{ grid-template-columns: 1fr; }}
  .stats-bar {{ gap: 12px; font-size: 0.75rem; }}
  .question-card {{ padding: 20px; }}
}}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>✂️ Schwarzkopf Study Bot</h1>
    <div class="subtitle">Igora Royal Color System Flashcards</div>
  </div>
  <div class="stats-bar" id="header-stats">
    <span>Streak: <b id="stat-streak">0</b></span>
    <span>Correct: <b id="stat-pct">0%</b></span>
  </div>
</div>

<!-- HOME SCREEN -->
<div class="screen active" id="screen-home">
  <div class="page-wrap">
    <h2 class="home-title">Pick a Topic</h2>
    <p class="home-sub">Choose what you want to quiz yourself on — 10 questions per round.</p>
    <div class="topic-grid" id="topic-grid"></div>
    <button class="start-btn" id="start-btn" onclick="startQuiz()" disabled>Choose a topic above</button>
    <div class="start-loading" id="start-loading" style="display:none">Generating questions… this takes a few seconds ✨</div>
  </div>
</div>

<!-- QUIZ SCREEN -->
<div class="screen" id="screen-quiz">
  <div class="page-wrap">
    <div class="quiz-header">
      <div class="quiz-topic-label" id="quiz-topic-label"></div>
      <div class="quiz-progress" id="quiz-progress"></div>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>

    <div class="question-card">
      <div class="question-num" id="question-num"></div>
      <div class="question-text" id="question-text"></div>
      <div class="options-list" id="options-list"></div>
    </div>

    <div class="grade-area" id="grade-area">
      <div class="grade-badge" id="grade-badge"></div>
      <div class="grade-explanation" id="grade-explanation"></div>
    </div>

    <button class="next-btn" id="next-btn" onclick="nextQuestion()" style="display:none"></button>
  </div>
</div>

<!-- RESULTS SCREEN -->
<div class="screen" id="screen-results">
  <div class="page-wrap">
    <div class="results-score">
      <div class="score-circle">
        <div class="score-pct" id="res-pct"></div>
        <div class="score-label" id="res-label"></div>
      </div>
      <p class="results-message" id="res-message"></p>
    </div>
    <h3 class="breakdown-title">Question Breakdown</h3>
    <div class="breakdown-list" id="breakdown-list"></div>
    <div class="results-actions">
      <button class="action-btn primary" onclick="tryAgain()">Try Again</button>
      <button class="action-btn secondary" onclick="goHome()">Change Topic</button>
    </div>
  </div>
</div>

<script>
const TOPICS = {topics_json};

let selectedTopic = null;
let sessionId = null;
let currentQuestion = null;
let currentIndex = 0;
let totalQuestions = 0;
let answered = false;
let lastTopic = null;

function showScreen(id) {{
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + id).classList.add('active');
  window.scrollTo(0, 0);
}}

async function loadStats() {{
  try {{
    const r = await fetch('/stats');
    const s = await r.json();
    document.getElementById('stat-streak').textContent = s.current_streak || 0;
    const pct = s.total_answered > 0
      ? Math.round((s.total_correct / s.total_answered) * 100)
      : 0;
    document.getElementById('stat-pct').textContent = pct + '%';
    // Update topic scores in grid
    TOPICS.forEach(t => {{
      const scoreEl = document.getElementById('score-' + t.id);
      if (scoreEl && s.by_topic && s.by_topic[t.id]) {{
        const bt = s.by_topic[t.id];
        if (bt.answered > 0) {{
          const p = Math.round((bt.correct / bt.answered) * 100);
          scoreEl.textContent = bt.correct + '/' + bt.answered + ' correct (' + p + '%)';
        }}
      }}
    }});
  }} catch(e) {{}}
}}

function renderTopicGrid() {{
  const grid = document.getElementById('topic-grid');
  grid.innerHTML = TOPICS.map(t => `
    <div class="topic-card" id="card-${{t.id}}" onclick="selectTopic('${{t.id}}')">
      <h3>${{t.label}}</h3>
      <p>${{t.desc}}</p>
      <div class="topic-score" id="score-${{t.id}}"></div>
    </div>
  `).join('');
}}

function selectTopic(topicId) {{
  selectedTopic = topicId;
  document.querySelectorAll('.topic-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('card-' + topicId).classList.add('selected');
  const btn = document.getElementById('start-btn');
  btn.disabled = false;
  btn.textContent = 'Start Quiz →';
}}

async function startQuiz() {{
  if (!selectedTopic) return;
  lastTopic = selectedTopic;
  const btn = document.getElementById('start-btn');
  const loading = document.getElementById('start-loading');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  loading.style.display = 'block';

  try {{
    const r = await fetch('/quiz/start', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{topic: selectedTopic}}),
    }});
    const data = await r.json();
    if (data.error) throw new Error(data.error);

    sessionId = data.session_id;
    totalQuestions = data.total;
    currentIndex = 0;

    document.getElementById('quiz-topic-label').textContent = data.topic_label;
    displayQuestion(data.question, 0);
    showScreen('quiz');
  }} catch(e) {{
    alert('Error generating questions: ' + e.message);
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Start Quiz →';
    loading.style.display = 'none';
  }}
}}

function displayQuestion(q, index) {{
  currentQuestion = q;
  currentIndex = index;
  answered = false;

  document.getElementById('question-num').textContent = 'Question ' + (index + 1);
  document.getElementById('question-text').textContent = q.question;
  document.getElementById('quiz-progress').textContent = (index + 1) + ' / ' + totalQuestions;

  const fill = ((index) / totalQuestions) * 100;
  document.getElementById('progress-fill').style.width = fill + '%';

  const opts = document.getElementById('options-list');
  const letters = ['A','B','C','D'];
  opts.innerHTML = q.options.map((opt, i) => `
    <button class="option-btn" data-letter="${{letters[i]}}" onclick="submitAnswer('${{letters[i]}}')">
      <span class="option-letter">${{letters[i]}}</span>
      ${{opt}}
    </button>
  `).join('');

  document.getElementById('grade-area').classList.remove('show');
  document.getElementById('next-btn').style.display = 'none';
}}

async function submitAnswer(letter) {{
  if (answered) return;
  answered = true;

  // Highlight selected
  document.querySelectorAll('.option-btn').forEach(b => {{
    b.disabled = true;
    if (b.dataset.letter === letter) b.classList.add('selected');
  }});

  const r = await fetch('/quiz/grade', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{session_id: sessionId, answer: letter}}),
  }});
  const data = await r.json();

  // Show correct/wrong highlighting
  document.querySelectorAll('.option-btn').forEach(b => {{
    if (b.dataset.letter === data.correct_answer) b.classList.add('correct-opt');
    else if (b.dataset.letter === letter && data.grade !== 'correct') b.classList.add('wrong-opt');
  }});

  // Show grade area
  const badge = document.getElementById('grade-badge');
  badge.className = 'grade-badge ' + data.grade;
  badge.textContent = data.grade === 'correct' ? '✓ Correct!' : '✗ Incorrect';
  document.getElementById('grade-explanation').textContent = data.explanation;
  document.getElementById('grade-area').classList.add('show');

  // Next button
  const nextBtn = document.getElementById('next-btn');
  nextBtn.style.display = 'block';
  if (data.has_next) {{
    nextBtn.textContent = 'Next Question →';
    nextBtn._next = data.next_question;
    nextBtn._nextIndex = data.next_index;
  }} else {{
    nextBtn.textContent = 'See Results →';
    nextBtn._next = null;
  }}

  loadStats();
}}

function nextQuestion() {{
  const btn = document.getElementById('next-btn');
  if (btn._next) {{
    displayQuestion(btn._next, btn._nextIndex);
  }} else {{
    fetchResults();
  }}
}}

async function fetchResults() {{
  document.getElementById('next-btn').textContent = 'Loading results…';
  document.getElementById('next-btn').disabled = true;

  const r = await fetch('/quiz/summary', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{session_id: sessionId}}),
  }});
  const data = await r.json();

  document.getElementById('res-pct').textContent = data.pct + '%';
  document.getElementById('res-label').textContent = data.correct + '/' + data.total;
  document.getElementById('res-message').textContent = data.message;

  // Breakdown
  const list = document.getElementById('breakdown-list');
  list.innerHTML = data.breakdown.map(item => `
    <div class="breakdown-item ${{item.grade}}">
      <div class="breakdown-q">${{item.index}}. ${{item.question}}</div>
      <div class="breakdown-detail">
        ${{item.grade === 'correct'
          ? `<span style="color:var(--correct)">✓ You answered: ${{item.user_answer}}</span>`
          : `<span style="color:var(--wrong)">✗ You answered: ${{item.user_answer}} · <span class="ans-label">Correct: ${{item.correct_answer}}</span></span>`
        }} — ${{item.explanation}}
      </div>
    </div>
  `).join('');

  showScreen('results');
  loadStats();
  renderTopicGrid();
  loadStats();
}}

function tryAgain() {{
  selectedTopic = lastTopic;
  showScreen('home');
  renderTopicGrid();
  loadStats();
  if (selectedTopic) {{
    setTimeout(() => selectTopic(selectedTopic), 50);
  }}
}}

function goHome() {{
  selectedTopic = null;
  sessionId = null;
  showScreen('home');
  renderTopicGrid();
  loadStats();
  document.getElementById('start-btn').disabled = true;
  document.getElementById('start-btn').textContent = 'Choose a topic above';
}}

// Init
renderTopicGrid();
loadStats();
</script>
</body>
</html>""".replace("{topics_json}", topics_json)

if __name__ == "__main__":
    app.run(port=5003, debug=True)
