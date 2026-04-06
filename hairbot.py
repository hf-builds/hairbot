import os
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import anthropic

app = Flask(__name__)

PAYROLL_FILE = os.path.expanduser("~/Documents/hairbot/payroll.json")
CHATS_DIR    = os.path.expanduser("~/Documents/hairbot/chats")
MEMORY_FILE  = os.path.expanduser("~/Documents/hairbot/memory.json")
os.makedirs(CHATS_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are a PhD-level Schwarzkopf color expert and educator. Your only job is to help a hairstylist deeply understand Schwarzkopf's color lines and how to use them. You know every product line Schwarzkopf makes: Igora Royal (permanent), Igora Vibrance (demi-permanent), Igora Color10 (10-minute), TBH (ammonia-free), BlondMe (blonde specialist), Igora Zero Amm (ammonia-free permanent), Igora Royal Absolutes (mature hair), Igora Royal Highlifts, Igora Royal Fashion Lights, Igora Royal Silver Whites, Igora Vario Blond (lightener). All Igora lines use the same numbering system.
THE NUMBER SYSTEM: The number before the dash is the depth/level (1=black, 2=very dark brown, 3=dark brown, 4=medium brown, 5=light brown, 6=dark blonde, 7=medium blonde, 8=light blonde, 9=extra light blonde, 9.5=ultra light blonde). The first digit after the dash is the PRIMARY tone. The second digit (if present) is the SECONDARY tone. PRIMARY TONES: 0=Natural, 1=Ash/Cendré (cool, eliminates warmth), 2=Iridescent (pearl/violet shimmer, multi-dimensional cool), 3=Matt (flat, no shine, olive/green-cool), 4=Beige (warm-neutral), 5=Gold (warm yellow-gold), 6=Chocolate/Mahogany (warm red-brown), 7=Copper (warm orange-red), 8=Red (true red), 9=Violet/Extra Red. EXTENDED TONE CODES: 00=Natural Extra (extra coverage for resistant grey), 11=Ash Extra, 12=Ash Beige, 13=Cendré Plus (very cool strong ash), 16=Ash Brown (cool ash with brown base), 19=Violet Ash (smoky cool violet-ash), 21=Ash Iridescent, 22=Iridescent Extra, 24=Iridescent Beige, 29=Violet Iridescent, 33=Matt Extra, 42=Beige Iridescent, 46=Beige Chocolate, 48=Beige Red, 55=Gold Extra, 57=Gold Copper, 63=Chocolate Matt, 65=Chocolate Gold, 67=Chocolate Copper, 68=Chocolate Red, 76=Copper Chocolate, 77=Copper Extra, 84=Red Beige, 88=Red Extra, 98=Violet Red, 99=Violet Extra. Double same digits always mean Extra Intense. Two different digits = blend, first digit is dominant tone (-65 = chocolate dominant, gold secondary = chocolate gold; -68 = chocolate dominant, red secondary = chocolate red; -16 = ash dominant, chocolate secondary = ash brown).
THE SPECIALITY RANGE: 0-series with no level = additives. Neutralisers (0-11, 0-22, 0-33): added to any shade to cancel unwanted warmth/tone. The higher the level of hair being colored, the LESS neutraliser you need (level 8-9: up to 5% of formula; level 6-7: up to 15%; level 1-5: up to 25%). Boosters (0-55, 0-77, 0-88, 0-89, 0-99): intensify fashion tones, can be added to any shade. Extracts (D-0, E-0, E-1): D-0 is a diluter/pastelfier, E-0/E-1 are fashion extracts. 9.5 series are pastel shades for very light bases. Highlifts (10-series): up to 4 levels of lift, used on base 7-8 only, always with 40vol developer. Special Blonde (12-series): up to 5 levels of lift, used on base 6-8, always with 40vol developer. NEVER use Highlifts on previously colored hair.
THE UNDERLYING PIGMENT LADDER (what hair actually lifts to during lightening): Level 1-3=black/blue-black, Level 4=red, Level 5=red-orange, Level 6=orange, Level 7=orange-yellow, Level 8=yellow, Level 9+=pale yellow. This is CRITICAL for choosing the right toner or formula. If a client lifts to pale yellow (level 9+), a toner goes on clean — minimal neutralization needed. If they lift to orange-yellow (level 7), you must neutralize both orange (needs blue/ash) AND yellow (needs violet) to achieve a true cool result. If lifting to orange (level 6), you need strong ash/blue neutralization.
NEUTRALIZATION COLOR WHEEL: Blue/ash cancels orange. Violet/purple cancels yellow. Green cancels red. Red-orange cancels blue-green. Always identify what the hair has LIFTED TO before choosing a toner. The goal toner shade must account for what's underneath, not just the desired end result.
DEVELOPER VOLUMES (Igora Royal Oil Developer): 10vol (3%): Deposit only — for coloring darker, or pastel toning with 9.5-shades on previously bleached/highlighted hair. No lift. 20vol (6%): Tone-on-tone, up to 1 level lighter. Standard grey coverage. Exception: -00 shades always require 30vol. 30vol (9%): 1-2 levels lift with standard shades. Also used for 2-3 levels lift with 10-series Highlifts, and 3-4 levels lift with 12-series Special Blonde. 40vol (12%): 2-3 levels lift with standard shades. 3-4 levels lift with 10-series. 4-5 levels lift with 12-series. IGORA VIBRANCE DEVELOPER: Vibrance does NOT use Igora Royal developer. It uses its own Activator Lotion or Activator Gel at 1.9% / 6 Vol. Always 1:1 mixing ratio. Development time 5-20 minutes. Ammonia-free, demi-permanent. MIXING RATIOS: Standard Igora Royal: 1:1 (60ml color + 60ml developer). Igora Royal 10-series Highlifts: 1:1 with either 30vol or 40vol (30vol = 2-3 levels lift, 40vol = 3-4 levels lift). Igora Royal 12-series Special Blonde: 1:2 (60ml color + 120ml developer) with either 30vol (3-4 levels lift) or 40vol (4-5 levels lift). Igora Vibrance: 1:1 with 6vol Activator Lotion or Activator Gel. Neutralisers: add to formula and increase developer to match (e.g. 60ml shade + 9ml neutraliser = 69ml developer).
When answering, always: (1) explain the WHY behind your recommendation, not just the what. (2) Consider what the client's hair has lifted to as a starting point. (3) Suggest specific shade numbers when relevant. (4) Flag any warnings (e.g. never Highlift on colored hair). Be conversational, educational, and encouraging — this stylist is building deep expertise."""

FORMULA_SYSTEM_PROMPT = SYSTEM_PROMPT + """\n\nYou are now in Formula Builder mode. The user will provide structured inputs about a client. Your job is to return a complete, precise, professional formula. Always explain the underlying pigment the hair will pass through during lifting and how your formula accounts for it. Always flag any warnings. Format your response clearly with labeled sections using markdown bold headers: **Formula**, **Developer**, **Mixing Ratio**, **Processing Time**, **Warnings**, and **Why This Works**. If there is a strong secondary option, add an **Alternative Formula** section. Be specific with shade numbers and ml amounts."""


# ── Payroll helpers ──────────────────────────────────────────────────────────

def load_payroll():
    if os.path.exists(PAYROLL_FILE):
        with open(PAYROLL_FILE) as f:
            return json.load(f)
    return []

def save_payroll(data):
    with open(PAYROLL_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Chat + memory helpers ────────────────────────────────────────────────────

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return []

def save_memory(facts):
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2)

def build_system_prompt():
    memory = load_memory()
    prompt = SYSTEM_PROMPT
    if memory:
        memory_str = "\n".join(f"- {fact}" for fact in memory)
        prompt += f"\n\nTHINGS YOU REMEMBER FROM PAST CONVERSATIONS:\n{memory_str}"
    return prompt

def list_chats():
    chats = []
    try:
        files = sorted(
            [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")],
            reverse=True,
        )
        for fname in files:
            path = os.path.join(CHATS_DIR, fname)
            with open(path) as f:
                chat = json.load(f)
            chats.append({
                "id":         chat["id"],
                "title":      chat.get("title", ""),
                "created_at": chat["created_at"],
            })
    except Exception:
        pass
    return chats

def get_chat(chat_id):
    if "/" in chat_id or ".." in chat_id:
        return None
    path = os.path.join(CHATS_DIR, chat_id + ".json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def save_chat(chat):
    path = os.path.join(CHATS_DIR, chat["id"] + ".json")
    with open(path, "w") as f:
        json.dump(chat, f, indent=2)

def make_chat():
    now = datetime.now()
    chat_id = "chat_" + now.strftime("%Y%m%d_%H%M%S_") + os.urandom(3).hex()
    chat = {
        "id":         chat_id,
        "title":      "",
        "created_at": now.isoformat(),
        "messages":   [],
    }
    save_chat(chat)
    return chat

def generate_title(first_user_msg):
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=15,
            system="Generate a very short title (3-5 words max) for a hairstylist color consultation. Return ONLY the title text, nothing else.",
            messages=[{"role": "user", "content": first_user_msg}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return "Color Consultation"

def extract_memory_bg(messages):
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        tail = messages[-6:]
        convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in tail)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system='Extract reusable facts from this hair color chat (formulas, techniques, client notes). Return a JSON array of short strings. Return [] if nothing notable. Example: ["7-65 with 30vol gave great lift on natural level 5 hair"]',
            messages=[{"role": "user", "content": convo}],
        )
        new_facts = json.loads(resp.content[0].text.strip())
        if new_facts:
            facts = load_memory()
            facts.extend(new_facts)
            save_memory(facts[-50:])
    except Exception:
        pass


# ── HTML ─────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Hairbot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>
<style>
  :root {
    --rose:       #c9848a;
    --rose-dark:  #a86068;
    --rose-light: #f8eced;
    --rose-xl:    #fdf5f5;
    --bg:         #fafaf8;
    --border:     #ede8e3;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: #1a1a1a; min-height: 100vh; }

  /* ── Tab bar ── */
  .tab-bar { display: flex; border-bottom: 2px solid var(--border); background: #fff; position: sticky; top: 0; z-index: 100; }
  .tab-btn { flex: 1; padding: 13px 4px; font-size: 13px; font-weight: 600; background: none; border: none; color: #999; cursor: pointer; transition: color 0.2s; border-bottom: 3px solid transparent; margin-bottom: -2px; font-family: inherit; }
  .tab-btn.active { color: var(--rose); border-bottom-color: var(--rose); }
  .tab-content { display: none; }
  .tab-content.active { display: flex; flex-direction: column; }

  /* ── Chat tab — row layout ── */
  #chat-tab.active { flex-direction: row; height: calc(100vh - 55px); overflow: hidden; }

  /* ── Sidebar ── */
  .sidebar { width: 260px; background: #fff; border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; overflow: hidden; }
  .sidebar-header { padding: 14px 12px 10px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .sidebar-label { font-size: 11px; font-weight: 700; color: #bbb; text-transform: uppercase; letter-spacing: 0.8px; }
  .new-chat-side-btn { background: var(--rose); color: #fff; border: none; border-radius: 20px; padding: 6px 14px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background 0.2s; flex-shrink: 0; }
  .new-chat-side-btn:hover { background: var(--rose-dark); }
  .chat-list { flex: 1; overflow-y: auto; padding: 6px 0; }
  .chat-item { padding: 10px 14px; cursor: pointer; border-radius: 10px; margin: 2px 6px; transition: background 0.15s; }
  .chat-item:hover { background: var(--rose-light); }
  .chat-item.active { background: var(--rose-light); border-left: 3px solid var(--rose); padding-left: 11px; }
  .chat-item-title { font-size: 13px; font-weight: 600; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chat-item-date { font-size: 11px; color: #bbb; margin-top: 2px; }
  .chat-list-empty { padding: 20px 14px; font-size: 13px; color: #ccc; text-align: center; }

  /* Sidebar overlay (mobile) */
  .sidebar-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 199; }
  .sidebar-overlay.open { display: block; }

  /* ── Chat main ── */
  .chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
  .chat-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); background: #fff; gap: 10px; }
  .hamburger { background: none; border: none; font-size: 21px; cursor: pointer; color: #888; padding: 0; line-height: 1; display: none; flex-shrink: 0; }
  .chat-header h2 { font-size: 16px; font-weight: 700; color: #1a1a1a; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chat-messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }

  /* ── Messages ── */
  .msg { padding: 10px 14px; border-radius: 18px; font-size: 15px; line-height: 1.55; word-wrap: break-word; }
  .msg.user { align-self: flex-end; background: var(--rose); color: #fff; border-bottom-right-radius: 4px; max-width: 82%; white-space: pre-wrap; }
  .msg-wrap { display: flex; align-items: flex-start; gap: 8px; align-self: flex-start; max-width: 88%; }
  .msg-avatar { font-size: 18px; flex-shrink: 0; margin-top: 5px; }
  .msg.assistant { background: #fff; color: #1a1a1a; border-bottom-left-radius: 4px; box-shadow: 0 1px 5px rgba(0,0,0,0.07); }
  .msg.thinking { background: #f5f0ee; color: #aaa; border-bottom-left-radius: 4px; font-style: italic; }

  /* Markdown inside assistant bubble */
  .msg.assistant p { margin: 0 0 8px; }
  .msg.assistant p:last-child { margin-bottom: 0; }
  .msg.assistant ul, .msg.assistant ol { padding-left: 18px; margin: 4px 0 8px; }
  .msg.assistant li { margin: 2px 0; }
  .msg.assistant strong { font-weight: 700; }
  .msg.assistant em { font-style: italic; }
  .msg.assistant code { background: var(--rose-light); border-radius: 4px; padding: 1px 5px; font-size: 13px; font-family: 'Courier New', monospace; }
  .msg.assistant pre { background: var(--rose-light); border-radius: 8px; padding: 10px; overflow-x: auto; margin: 6px 0; }
  .msg.assistant pre code { background: none; padding: 0; }
  .msg.assistant h1, .msg.assistant h2, .msg.assistant h3 { font-weight: 700; margin: 10px 0 4px; font-size: 15px; }
  .msg.assistant blockquote { border-left: 3px solid var(--rose); padding-left: 10px; color: #777; margin: 4px 0; font-style: italic; }
  .msg.assistant hr { border: none; border-top: 1px solid var(--border); margin: 8px 0; }

  /* Chat input */
  .chat-input-area { padding: 12px 16px; border-top: 1px solid var(--border); background: #fff; display: flex; gap: 10px; align-items: flex-end; }
  .chat-input-area textarea { flex: 1; border: 1.5px solid #e0d8d5; border-radius: 22px; padding: 10px 16px; font-size: 15px; font-family: inherit; resize: none; outline: none; max-height: 120px; line-height: 1.4; transition: border-color 0.2s; background: var(--bg); }
  .chat-input-area textarea:focus { border-color: var(--rose); }
  .send-btn { background: var(--rose); color: #fff; border: none; border-radius: 50%; width: 42px; height: 42px; font-size: 20px; cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center; transition: background 0.2s; }
  .send-btn:hover { background: var(--rose-dark); }
  .send-btn:disabled { background: #e8c8ca; cursor: default; }

  /* Empty state */
  .empty-chat { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 10px; padding: 40px 20px; text-align: center; }
  .empty-chat .icon { font-size: 48px; }
  .empty-chat p { font-size: 15px; line-height: 1.5; max-width: 280px; color: #bbb; }

  /* ── Payroll tab ── */
  #payroll-tab { padding: 16px; gap: 0; overflow-y: auto; background: var(--bg); }
  .payroll-form { background: var(--rose-xl); border: 1.5px solid #ecd5d6; border-radius: 16px; padding: 16px; margin-bottom: 24px; }
  .payroll-form h2 { font-size: 17px; font-weight: 700; margin-bottom: 14px; color: #1a1a1a; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .form-group { display: flex; flex-direction: column; gap: 5px; }
  .form-group.full { grid-column: 1 / -1; }
  .form-group label { font-size: 12px; font-weight: 700; color: var(--rose-dark); text-transform: uppercase; letter-spacing: 0.5px; }
  .form-group input { border: 1.5px solid #e0d8d5; border-radius: 10px; padding: 9px 12px; font-size: 15px; font-family: inherit; outline: none; background: #fff; transition: border-color 0.2s; }
  .form-group input:focus { border-color: var(--rose); }
  .submit-btn { width: 100%; margin-top: 14px; background: var(--rose); color: #fff; border: none; border-radius: 12px; padding: 13px; font-size: 16px; font-weight: 700; cursor: pointer; transition: background 0.2s; font-family: inherit; }
  .submit-btn:hover { background: var(--rose-dark); }

  .section-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; color: #1a1a1a; }
  .table-wrap { overflow-x: auto; border-radius: 12px; border: 1.5px solid var(--border); margin-bottom: 20px; background: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 500px; }
  th { background: var(--rose); color: #fff; padding: 10px 12px; text-align: left; font-weight: 600; font-size: 12px; }
  td { padding: 9px 12px; border-bottom: 1px solid #f5f0ee; }
  tr:last-child td { border-bottom: none; }
  tr:nth-child(even) td { background: var(--rose-xl); }

  .summary-cards { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
  .card { background: #fff; border-radius: 12px; padding: 14px 12px; text-align: center; border: 1.5px solid var(--border); }
  .card.highlight { background: var(--rose); color: #fff; border-color: var(--rose); }
  .card .label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.7; margin-bottom: 4px; }
  .card .value { font-size: 18px; font-weight: 800; }
  .card.highlight .label { opacity: 0.85; }
  .no-data { color: #ccc; text-align: center; padding: 20px; font-size: 14px; }

  /* Current week */
  #cur-week-table tr:nth-child(even) td { background: #fff; }
  .cw-empty { color: #ccc; text-align: center; padding: 20px; font-size: 14px; }

  /* History toggle */
  .history-divider { border-top: 1.5px solid var(--border); margin: 8px 0 18px; display: flex; align-items: center; justify-content: center; }
  .history-toggle { background: #f5f0ee; color: #777; border: 1.5px solid #e0d8d5; border-radius: 20px; padding: 7px 20px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: -14px; transition: all 0.2s; font-family: inherit; }
  .history-toggle:hover { background: var(--rose-light); color: var(--rose); border-color: #ecd5d6; }

  /* Collapsible history weeks */
  .hist-week { border: 1.5px solid var(--border); border-radius: 12px; margin-bottom: 10px; overflow: hidden; background: #fff; }
  .hist-week summary { display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; background: #f5f0ee; cursor: pointer; list-style: none; font-size: 13px; font-weight: 600; color: #555; user-select: none; gap: 8px; }
  .hist-week summary::-webkit-details-marker { display: none; }
  .hist-week summary::before { content: '\\25B6'; font-size: 10px; color: #bbb; flex-shrink: 0; transition: transform 0.2s; }
  .hist-week[open] summary::before { transform: rotate(90deg); }
  .hist-week-total { font-size: 14px; font-weight: 800; color: var(--rose); white-space: nowrap; }
  .hist-week-body { overflow-x: auto; }
  .hist-week-body table { min-width: 420px; }
  .hist-week-body td { padding: 8px 12px; border-bottom: 1px solid #f5f0ee; }
  .hist-week-body tr:nth-child(even) td { background: var(--rose-xl); }
  .hist-week-body tr:last-child td { border-bottom: none; }
  .hist-week-body th { font-size: 11px; }

  /* Monthly summary */
  .monthly-summary-title { font-size: 15px; font-weight: 700; margin: 20px 0 10px; color: #1a1a1a; }

  /* Payroll edit mode */
  .payroll-form.editing { background: #fffbeb; border-color: #f59e0b; }
  .payroll-form.editing h2::after { content: ' \2014 Editing'; font-size: 13px; font-weight: 500; color: #b45309; }
  .btn-row { display: flex; gap: 8px; margin-top: 14px; }
  .submit-btn { flex: 1; margin-top: 0; }
  .cancel-btn { flex: 0 0 auto; background: #f5f0ee; color: #777; border: 1.5px solid #e0d8d5; border-radius: 12px; padding: 13px 18px; font-size: 15px; font-weight: 600; cursor: pointer; font-family: inherit; }
  .cancel-btn:hover { background: var(--border); }
  .edit-btn { background: none; border: 1.5px solid #ecd5d6; color: var(--rose); border-radius: 8px; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; font-family: inherit; }
  .edit-btn:hover { background: var(--rose-light); }

  /* ── Shade Chart ── */
  #shade-tab { height: calc(100vh - 55px); overflow: hidden; background: var(--bg); }
  .sc-filters { padding: 10px 16px; display: flex; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--border); background: #fff; flex-shrink: 0; }
  .sc-filters input, .sc-filters select { border: 1.5px solid #e0d8d5; border-radius: 10px; padding: 8px 11px; font-size: 13px; font-family: inherit; outline: none; background: #fff; color: #1a1a1a; transition: border-color 0.2s; }
  .sc-filters input { flex: 1; min-width: 130px; }
  .sc-filters select { flex: 1; min-width: 155px; }
  .sc-filters input:focus, .sc-filters select:focus { border-color: var(--rose); }
  .sc-count-row { padding: 6px 16px; font-size: 12px; color: #bbb; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  #shade-tab .sc-table-wrap { flex: 1; overflow: auto; }
  #shade-tab table { min-width: 720px; }
  .sc-note { font-size: 11px; color: #999; line-height: 1.4; }
  .sc-shade { font-weight: 700; font-size: 14px; letter-spacing: 0.3px; }

  /* ── Formula Builder ── */
  #formula-tab { padding: 16px; overflow-y: auto; background: var(--bg); }
  .fb-form { background: var(--rose-xl); border: 1.5px solid #ecd5d6; border-radius: 16px; padding: 16px; margin-bottom: 20px; }
  .fb-form h2 { font-size: 17px; font-weight: 700; margin-bottom: 16px; color: #1a1a1a; }
  .fb-row { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
  .fb-row label { font-size: 12px; font-weight: 700; color: var(--rose-dark); text-transform: uppercase; letter-spacing: 0.5px; }
  .fb-row select, .fb-row textarea { border: 1.5px solid #e0d8d5; border-radius: 10px; padding: 9px 12px; font-size: 15px; font-family: inherit; outline: none; background: #fff; color: #1a1a1a; transition: border-color 0.2s; width: 100%; }
  .fb-row select:focus, .fb-row textarea:focus { border-color: var(--rose); }
  .fb-row textarea { resize: none; line-height: 1.4; }
  .fb-build-btn { width: 100%; background: var(--rose); color: #fff; border: none; border-radius: 12px; padding: 14px; font-size: 16px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background 0.2s; margin-top: 4px; }
  .fb-build-btn:hover { background: var(--rose-dark); }
  .fb-build-btn:disabled { background: #e8c8ca; cursor: default; }
  .fb-result { background: #fff; border-radius: 16px; border: 1.5px solid var(--border); border-top: 4px solid var(--rose); padding: 18px; margin-top: 4px; font-size: 15px; line-height: 1.55; }
  .fb-loading { background: #fff; border-radius: 16px; border: 1.5px solid var(--border); padding: 28px 16px; text-align: center; color: #bbb; font-size: 15px; font-style: italic; margin-top: 4px; }
  .fb-result p { margin: 0 0 8px; }
  .fb-result p:last-child { margin-bottom: 0; }
  .fb-result ul, .fb-result ol { padding-left: 18px; margin: 4px 0 8px; }
  .fb-result li { margin: 2px 0; }
  .fb-result strong { font-weight: 700; }
  .fb-result em { font-style: italic; }
  .fb-result h1, .fb-result h2, .fb-result h3 { font-weight: 700; margin: 14px 0 5px; font-size: 15px; color: var(--rose-dark); }
  .fb-result h1:first-child, .fb-result h2:first-child, .fb-result h3:first-child { margin-top: 0; }
  .fb-result code { background: var(--rose-light); border-radius: 4px; padding: 1px 5px; font-size: 13px; }
  .fb-result hr { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
  .fb-result blockquote { border-left: 3px solid var(--rose); padding-left: 10px; color: #666; margin: 6px 0; font-style: italic; }

  /* ── Mobile ── */
  @media (max-width: 600px) {
    .sidebar { position: fixed; left: 0; top: 55px; bottom: 0; z-index: 200; transform: translateX(-100%); transition: transform 0.25s ease; box-shadow: 4px 0 20px rgba(0,0,0,0.12); }
    .sidebar.open { transform: translateX(0); }
    .hamburger { display: block; }
  }
  @media (max-width: 360px) {
    .summary-cards { grid-template-columns: 1fr 1fr; }
    .card:last-child { grid-column: 1 / -1; }
    .form-grid { grid-template-columns: 1fr; }
    .form-group.full { grid-column: 1; }
  }
</style>
</head>
<body>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('chat')">Color Assistant</button>
  <button class="tab-btn" onclick="switchTab('payroll')">Payroll &amp; Tips</button>
  <button class="tab-btn" onclick="switchTab('shade')">Shade Chart</button>
  <button class="tab-btn" onclick="switchTab('formula')">Formula Builder</button>
</div>

<!-- ── Color Assistant Tab ── -->
<div id="chat-tab" class="tab-content active">
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-label">Chats</span>
      <button class="new-chat-side-btn" onclick="newChat()">+ New</button>
    </div>
    <div id="chat-list" class="chat-list">
      <div class="chat-list-empty">No conversations yet</div>
    </div>
  </div>
  <div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>
  <div class="chat-main">
    <div class="chat-header">
      <button class="hamburger" onclick="toggleSidebar()">&#9776;</button>
      <h2 id="chat-title">Color Assistant</h2>
    </div>
    <div class="chat-messages" id="messages">
      <div class="empty-chat" id="empty-state">
        <div class="icon">&#9986;&#65039;</div>
        <p>Ask me anything about Schwarzkopf color &mdash; formulas, numbering, toners, developers, neutralization...</p>
      </div>
    </div>
    <div class="chat-input-area">
      <textarea id="msg-input" rows="1" placeholder="Ask about color..." onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <button class="send-btn" id="send-btn" onclick="sendMessage()">&#8593;</button>
    </div>
  </div>
</div>

<!-- ── Payroll & Tips Tab ── -->
<div id="payroll-tab" class="tab-content">
  <div class="payroll-form">
    <h2>Log a Day</h2>
    <div class="form-grid">
      <div class="form-group full">
        <label>Date</label>
        <input type="date" id="entry-date">
      </div>
      <div class="form-group">
        <label>Pay</label>
        <input type="number" id="entry-pay" placeholder="0.00" step="0.01" min="0">
      </div>
      <div class="form-group">
        <label>Tips</label>
        <input type="number" id="entry-tips" placeholder="0.00" step="0.01" min="0">
      </div>
    </div>
    <div class="btn-row">
      <button class="submit-btn" id="payroll-submit-btn" onclick="submitPayroll()">Save Day</button>
      <button class="cancel-btn" id="payroll-cancel-btn" onclick="cancelEdit()" style="display:none">Cancel</button>
    </div>
  </div>

  <!-- Current Week -->
  <div class="section-title" id="cur-week-title">This Week</div>
  <div class="table-wrap">
    <table id="cur-week-table">
      <thead>
        <tr><th>Date</th><th>Day</th><th>Pay</th><th>Tips</th><th>Total Earned</th><th></th></tr>
      </thead>
      <tbody id="cur-week-body"></tbody>
    </table>
  </div>
  <div class="summary-cards" style="margin-bottom:24px">
    <div class="card">
      <div class="label">Total Pay</div>
      <div class="value" id="cw-pay">$0</div>
    </div>
    <div class="card">
      <div class="label">Total Tips</div>
      <div class="value" id="cw-tips">$0</div>
    </div>
    <div class="card highlight">
      <div class="label">Total Earned</div>
      <div class="value" id="cw-total">$0</div>
    </div>
  </div>

  <!-- History -->
  <div class="history-divider">
    <button class="history-toggle" id="history-toggle-btn" onclick="toggleHistory()">View History &#9660;</button>
  </div>
  <div id="history-section" style="display:none">
    <div id="history-weeks"></div>
    <div class="monthly-summary-title">Monthly Summary</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Month</th><th>Total Pay</th><th>Total Tips</th><th>Grand Total</th></tr>
        </thead>
        <tbody id="monthly-summary-body"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Shade Chart Tab ── -->
<div id="shade-tab" class="tab-content">
  <div class="sc-filters">
    <input type="text" id="sc-search" placeholder="Search shade (e.g. 7-65)" oninput="filterShades()">
    <select id="sc-line" onchange="filterShades()">
      <option value="">All Lines</option>
      <option value="R">Igora Royal</option>
      <option value="V">Igora Vibrance</option>
      <option value="C">Igora Color10</option>
      <option value="H">Igora Royal Highlifts</option>
      <option value="SB">Igora Royal Special Blonde</option>
      <option value="A">Igora Royal Absolutes</option>
      <option value="SW">Igora Royal Silver Whites</option>
      <option value="FL">Igora Royal Fashion Lights</option>
      <option value="SP">Speciality Range</option>
      <option value="AB">Igora Royal Absolutes Age Blend</option>
    </select>
    <select id="sc-level" onchange="filterShades()">
      <option value="">All Levels</option>
      <option value="1">1 - Black</option>
      <option value="2">2 - Very Dark Brown</option>
      <option value="3">3 - Dark Brown</option>
      <option value="4">4 - Medium Brown</option>
      <option value="5">5 - Light Brown</option>
      <option value="6">6 - Dark Blonde</option>
      <option value="7">7 - Medium Blonde</option>
      <option value="8">8 - Light Blonde</option>
      <option value="9">9 - Extra Light Blonde</option>
      <option value="9.5">9.5 - Ultra Light Blonde</option>
      <option value="specialty">Specialty - No Level</option>
    </select>
    <select id="sc-tone" onchange="filterShades()">
      <option value="">All Tones</option>
      <option value="0">0 Natural</option>
      <option value="00">00 Natural Extra</option>
      <option value="1">1 Ash / Cendré</option>
      <option value="11">11 Ash Extra</option>
      <option value="12">12 Ash Beige</option>
      <option value="13">13 Cendré Plus</option>
      <option value="16">16 Ash Brown</option>
      <option value="19">19 Violet Ash</option>
      <option value="2">2 Iridescent</option>
      <option value="21">21 Ash Iridescent</option>
      <option value="22">22 Iridescent Extra</option>
      <option value="24">24 Iridescent Beige</option>
      <option value="29">29 Violet Iridescent</option>
      <option value="3">3 Matt</option>
      <option value="33">33 Matt Extra</option>
      <option value="4">4 Beige</option>
      <option value="42">42 Beige Iridescent</option>
      <option value="46">46 Beige Chocolate</option>
      <option value="48">48 Beige Red</option>
      <option value="5">5 Gold</option>
      <option value="55">55 Gold Extra</option>
      <option value="57">57 Gold Copper</option>
      <option value="6">6 Chocolate</option>
      <option value="63">63 Chocolate Matt</option>
      <option value="65">65 Chocolate Gold</option>
      <option value="67">67 Chocolate Copper</option>
      <option value="68">68 Chocolate Red</option>
      <option value="7">7 Copper</option>
      <option value="76">76 Copper Chocolate</option>
      <option value="77">77 Copper Extra</option>
      <option value="8">8 Red</option>
      <option value="84">84 Red Beige</option>
      <option value="88">88 Red Extra</option>
      <option value="9">9 Violet</option>
      <option value="98">98 Violet Red</option>
      <option value="99">99 Violet Extra</option>
    </select>
  </div>
  <div class="sc-count-row"><span id="sc-count">Loading...</span></div>
  <div class="sc-table-wrap">
    <table id="shade-table">
      <thead>
        <tr>
          <th>Shade Number</th>
          <th>Level</th>
          <th>Primary Tone</th>
          <th>Secondary Tone</th>
          <th>Lines Available</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody id="shade-tbody"></tbody>
    </table>
  </div>
</div>

<!-- ── Formula Builder Tab ── -->
<div id="formula-tab" class="tab-content">
  <div class="fb-form">
    <h2>Build a Formula</h2>

    <div class="fb-row">
      <label>Current Hair Level</label>
      <select id="fb-current-level">
        <option value="Unknown">Unknown</option>
        <option value="1">1 — Black</option>
        <option value="2">2 — Very Dark Brown</option>
        <option value="3">3 — Dark Brown</option>
        <option value="4">4 — Medium Brown</option>
        <option value="5">5 — Light Brown</option>
        <option value="6">6 — Dark Blonde</option>
        <option value="7">7 — Medium Blonde</option>
        <option value="8">8 — Light Blonde</option>
        <option value="9">9 — Extra Light Blonde</option>
        <option value="9.5">9.5 — Ultra Light Blonde</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Current Hair Condition</label>
      <select id="fb-condition">
        <option value="Virgin / Natural">Virgin / Natural</option>
        <option value="Previously Colored">Previously Colored</option>
        <option value="Previously Lightened / Bleached">Previously Lightened / Bleached</option>
        <option value="Mixed — some colored, some not">Mixed — some colored, some not</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Grey Percentage</label>
      <select id="fb-grey">
        <option value="No Grey">No Grey</option>
        <option value="Up to 25% Grey">Up to 25% Grey</option>
        <option value="25–50% Grey">25–50% Grey</option>
        <option value="50–75% Grey">50–75% Grey</option>
        <option value="75–100% Grey">75–100% Grey</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Target Level</label>
      <select id="fb-target-level">
        <option value="">— Select —</option>
        <option value="1">1 — Black</option>
        <option value="2">2 — Very Dark Brown</option>
        <option value="3">3 — Dark Brown</option>
        <option value="4">4 — Medium Brown</option>
        <option value="5">5 — Light Brown</option>
        <option value="6">6 — Dark Blonde</option>
        <option value="7">7 — Medium Blonde</option>
        <option value="8">8 — Light Blonde</option>
        <option value="9">9 — Extra Light Blonde</option>
        <option value="9.5">9.5 — Ultra Light Blonde</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Target Tone</label>
      <select id="fb-target-tone">
        <option value="">— Select —</option>
        <option value="Natural">Natural</option>
        <option value="Ash / Cendré">Ash / Cendré</option>
        <option value="Iridescent">Iridescent</option>
        <option value="Matt">Matt</option>
        <option value="Beige">Beige</option>
        <option value="Gold">Gold</option>
        <option value="Chocolate">Chocolate</option>
        <option value="Chocolate Gold">Chocolate Gold</option>
        <option value="Chocolate Red">Chocolate Red</option>
        <option value="Copper">Copper</option>
        <option value="Red">Red</option>
        <option value="Violet">Violet</option>
        <option value="Silver / Grey">Silver / Grey</option>
        <option value="Blonde Lift Only (no tone)">Blonde Lift Only (no tone)</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Preferred Line</label>
      <select id="fb-line">
        <option value="Let AI decide">Let AI decide</option>
        <option value="Igora Royal">Igora Royal</option>
        <option value="Igora Vibrance">Igora Vibrance</option>
        <option value="Igora Color10">Igora Color10</option>
        <option value="Igora Royal Highlifts">Igora Royal Highlifts</option>
        <option value="Igora Royal Special Blonde">Igora Royal Special Blonde</option>
        <option value="Igora Royal Absolutes">Igora Royal Absolutes</option>
        <option value="BlondMe">BlondMe</option>
      </select>
    </div>

    <div class="fb-row">
      <label>Notes (optional)</label>
      <textarea id="fb-notes" rows="2" placeholder="e.g. warm skin tone, needs to process in 45 min, high porosity ends..."></textarea>
    </div>

    <button class="fb-build-btn" id="fb-build-btn" onclick="buildFormula()">&#10024; Build Formula</button>
  </div>

  <div id="fb-result-area"></div>
</div>

<script>
// Configure marked
marked.use({ breaks: true, gfm: true });

// ── Shared constants ──────────────────────────────────────────────────────────
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAY_NAMES   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

// ── Tabs ──────────────────────────────────────────────────────────────────────
let shadeRendered = false;

function switchTab(tab) {
  const names = ['chat','payroll','shade','formula'];
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', names[i] === tab);
  });
  document.getElementById('chat-tab').classList.toggle('active', tab === 'chat');
  document.getElementById('payroll-tab').classList.toggle('active', tab === 'payroll');
  document.getElementById('shade-tab').classList.toggle('active', tab === 'shade');
  document.getElementById('formula-tab').classList.toggle('active', tab === 'formula');
  if (tab === 'payroll') loadPayroll();
  if (tab === 'shade' && !shadeRendered) { renderShadeTable(); shadeRendered = true; }
}

// ── Chat ──────────────────────────────────────────────────────────────────────
let currentChatId = null;

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatChatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return DAY_NAMES[d.getDay()];
  return MONTH_NAMES[d.getMonth()] + ' ' + d.getDate();
}

function appendMsg(role, text) {
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();
  const container = document.getElementById('messages');

  if (role === 'user') {
    const div = document.createElement('div');
    div.className = 'msg user';
    div.textContent = text;
    container.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return div;
  } else {
    // assistant or thinking — wrap with avatar
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap';
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = '✂️';
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    if (role === 'assistant') {
      div.innerHTML = marked.parse(text);
    } else {
      div.textContent = text;
    }
    wrap.appendChild(avatar);
    wrap.appendChild(div);
    container.appendChild(wrap);
    wrap.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return wrap; // return wrap so caller can .remove() it
  }
}

async function updateChatList(activeId) {
  try {
    const res = await fetch('/chats');
    const chats = await res.json();
    const list = document.getElementById('chat-list');
    const cur = (activeId !== undefined) ? activeId : currentChatId;
    if (!chats.length) {
      list.innerHTML = '<div class="chat-list-empty">No conversations yet</div>';
      return;
    }
    list.innerHTML = chats.map(c => `
      <div class="chat-item${c.id === cur ? ' active' : ''}" onclick="loadChat('${escHtml(c.id)}')">
        <div class="chat-item-title">${escHtml(c.title || 'New Conversation')}</div>
        <div class="chat-item-date">${escHtml(formatChatDate(c.created_at))}</div>
      </div>
    `).join('');
  } catch (e) {
    // silently fail — sidebar is cosmetic
  }
}

async function newChat() {
  const res = await fetch('/chats/new', { method: 'POST' });
  const data = await res.json();
  currentChatId = data.id;
  document.getElementById('chat-title').textContent = 'Color Assistant';
  document.getElementById('messages').innerHTML =
    '<div class="empty-chat" id="empty-state"><div class="icon">&#9986;&#65039;</div><p>Ask me anything about Schwarzkopf color &mdash; formulas, numbering, toners, developers, neutralization...</p></div>';
  await updateChatList(currentChatId);
  closeSidebar();
}

async function loadChat(id) {
  currentChatId = id;
  const res = await fetch('/chats/' + encodeURIComponent(id));
  const chat = await res.json();
  document.getElementById('chat-title').textContent = chat.title || 'Color Assistant';
  const msgs = document.getElementById('messages');
  msgs.innerHTML = '';
  if (!chat.messages || chat.messages.length === 0) {
    msgs.innerHTML = '<div class="empty-chat" id="empty-state"><div class="icon">&#9986;&#65039;</div><p>Ask me anything about Schwarzkopf color &mdash; formulas, numbering, toners, developers, neutralization...</p></div>';
  } else {
    chat.messages.forEach(m => appendMsg(m.role, m.content));
  }
  await updateChatList(id);
  closeSidebar();
}

async function sendMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;

  // Auto-create a chat if none is active
  if (!currentChatId) {
    const r = await fetch('/chats/new', { method: 'POST' });
    const d = await r.json();
    currentChatId = d.id;
  }

  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;

  appendMsg('user', text);
  const thinkEl = appendMsg('thinking', 'Thinking...');

  try {
    const res = await fetch('/chats/' + encodeURIComponent(currentChatId) + '/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    thinkEl.remove();
    if (data.error) {
      appendMsg('assistant', 'Error: ' + data.error);
    } else {
      appendMsg('assistant', data.reply);
      if (data.title) {
        document.getElementById('chat-title').textContent = data.title;
      }
    }
    await updateChatList();
  } catch (e) {
    thinkEl.remove();
    appendMsg('assistant', 'Network error — please try again.');
  }

  document.getElementById('send-btn').disabled = false;
  document.getElementById('msg-input').focus();
}

// Load chat list on startup
window.addEventListener('load', () => updateChatList());

// ── Payroll ───────────────────────────────────────────────────────────────────
function fmt(n) { return '$' + Number(n).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ','); }

let editingDate = null;

function weekStart(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const daysSinceThu = (d.getDay() - 4 + 7) % 7;
  const thu = new Date(d);
  thu.setDate(d.getDate() - daysSinceThu);
  return thu;
}

function fmtDay(d) { return MONTH_NAMES[d.getMonth()] + ' ' + d.getDate(); }

function setEditMode(on) {
  const form   = document.querySelector('.payroll-form');
  const btn    = document.getElementById('payroll-submit-btn');
  const cancel = document.getElementById('payroll-cancel-btn');
  if (on) {
    form.classList.add('editing');
    btn.textContent = 'Update Entry';
    cancel.style.display = '';
  } else {
    form.classList.remove('editing');
    btn.textContent = 'Save Day';
    cancel.style.display = 'none';
    editingDate = null;
  }
}

function startEdit(date, pay, tips) {
  editingDate = date;
  document.getElementById('entry-date').value = date;
  document.getElementById('entry-pay').value  = pay;
  document.getElementById('entry-tips').value = tips;
  setEditMode(true);
  document.querySelector('.payroll-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function cancelEdit() {
  document.getElementById('entry-date').valueAsDate = new Date();
  document.getElementById('entry-pay').value  = '';
  document.getElementById('entry-tips').value = '';
  setEditMode(false);
}

function toggleHistory() {
  const section = document.getElementById('history-section');
  const btn     = document.getElementById('history-toggle-btn');
  const opening = section.style.display === 'none';
  section.style.display = opening ? '' : 'none';
  btn.innerHTML = opening ? 'Hide History &#9650;' : 'View History &#9660;';
}

function dayRow(r) {
  const d    = new Date(r.date + 'T12:00:00');
  const pay  = r.pay  || 0;
  const tips = r.tips || 0;
  return `<tr>
    <td>${fmtDay(d)}</td>
    <td>${DAY_NAMES[d.getDay()]}</td>
    <td>${fmt(pay)}</td>
    <td>${fmt(tips)}</td>
    <td>${fmt(pay + tips)}</td>
    <td><button class="edit-btn" onclick="startEdit('${r.date}',${pay},${tips})">Edit</button></td>
  </tr>`;
}

async function loadPayroll() {
  const res  = await fetch('/payroll');
  const all  = await res.json();
  const rows = all.filter(r => r.date);

  const todayStr = new Date().toISOString().slice(0, 10);
  const curThu   = weekStart(todayStr);
  const curKey   = curThu.toISOString().slice(0, 10);
  const curWed   = new Date(curThu); curWed.setDate(curThu.getDate() + 6);

  document.getElementById('cur-week-title').textContent =
    'This Week  \u00b7  Thu ' + fmtDay(curThu) + ' \u2013 Wed ' + fmtDay(curWed);

  const curRows = rows
    .filter(r => weekStart(r.date).toISOString().slice(0, 10) === curKey)
    .sort((a, b) => a.date.localeCompare(b.date));

  const cwBody = document.getElementById('cur-week-body');
  let cwPay = 0, cwTips = 0;
  if (curRows.length === 0) {
    cwBody.innerHTML = '<tr><td colspan="6" class="cw-empty">No entries this week yet.</td></tr>';
  } else {
    cwBody.innerHTML = curRows.map(r => {
      cwPay  += r.pay  || 0;
      cwTips += r.tips || 0;
      return dayRow(r);
    }).join('');
  }
  document.getElementById('cw-pay').textContent   = fmt(cwPay);
  document.getElementById('cw-tips').textContent  = fmt(cwTips);
  document.getElementById('cw-total').textContent = fmt(cwPay + cwTips);

  const histRows = rows.filter(r => weekStart(r.date).toISOString().slice(0, 10) < curKey);
  const histContainer = document.getElementById('history-weeks');
  if (histRows.length === 0) {
    histContainer.innerHTML =
      '<p style="color:#ccc;text-align:center;padding:16px;font-size:14px">No previous weeks yet.</p>';
  } else {
    const weeks = {};
    histRows.forEach(r => {
      const thu = weekStart(r.date);
      const key = thu.toISOString().slice(0, 10);
      if (!weeks[key]) weeks[key] = { thu, days: [] };
      weeks[key].days.push(r);
    });
    histContainer.innerHTML = Object.entries(weeks)
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([, week]) => {
        const thu  = week.thu;
        const wed  = new Date(thu); wed.setDate(thu.getDate() + 6);
        const label = 'Thu ' + fmtDay(thu) + ' \u2013 Wed ' + fmtDay(wed);
        const days  = week.days.slice().sort((a, b) => a.date.localeCompare(b.date));
        let wPay = 0, wTips = 0;
        const bodyRows = days.map(r => {
          wPay  += r.pay  || 0;
          wTips += r.tips || 0;
          return dayRow(r);
        }).join('');
        return `<details class="hist-week">
          <summary>
            <span>${label}</span>
            <span class="hist-week-total">${fmt(wPay + wTips)}</span>
          </summary>
          <div class="hist-week-body">
            <table>
              <thead><tr><th>Date</th><th>Day</th><th>Pay</th><th>Tips</th><th>Total</th><th></th></tr></thead>
              <tbody>${bodyRows}</tbody>
            </table>
          </div>
        </details>`;
      }).join('');
  }

  const months = {};
  rows.forEach(r => {
    const d   = new Date(r.date + 'T12:00:00');
    const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    if (!months[key]) months[key] = { label: MONTH_NAMES[d.getMonth()] + ' ' + d.getFullYear(), pay: 0, tips: 0 };
    months[key].pay  += r.pay  || 0;
    months[key].tips += r.tips || 0;
  });
  const mSorted = Object.entries(months).sort((a, b) => b[0].localeCompare(a[0]));
  const mBody   = document.getElementById('monthly-summary-body');
  mBody.innerHTML = mSorted.length === 0
    ? '<tr><td colspan="4" class="no-data">No data yet.</td></tr>'
    : mSorted.map(([, m]) => `<tr>
        <td><strong>${m.label}</strong></td>
        <td>${fmt(m.pay)}</td>
        <td>${fmt(m.tips)}</td>
        <td><strong>${fmt(m.pay + m.tips)}</strong></td>
      </tr>`).join('');
}

async function submitPayroll() {
  if (editingDate) {
    const date = document.getElementById('entry-date').value;
    const pay  = parseFloat(document.getElementById('entry-pay').value)  || 0;
    const tips = parseFloat(document.getElementById('entry-tips').value) || 0;
    if (!date) { alert('Please select a date.'); return; }
    const res = await fetch('/payroll/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_date: editingDate, date, pay, tips }),
    });
    const data = await res.json();
    if (data.ok) { cancelEdit(); loadPayroll(); }
    else alert('Error updating: ' + (data.error || 'unknown'));
  } else {
    const date = document.getElementById('entry-date').value;
    const pay  = parseFloat(document.getElementById('entry-pay').value)  || 0;
    const tips = parseFloat(document.getElementById('entry-tips').value) || 0;
    if (!date) { alert('Please select a date.'); return; }
    const res = await fetch('/payroll', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, pay, tips }),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById('entry-date').valueAsDate = new Date();
      document.getElementById('entry-pay').value  = '';
      document.getElementById('entry-tips').value = '';
      loadPayroll();
    } else {
      alert('Error saving: ' + (data.error || 'unknown'));
    }
  }
}

document.getElementById('entry-date').valueAsDate = new Date();

// ── Shade Chart ───────────────────────────────────────────────────────────────

const TONE_MAP = {
  "0":"Natural","00":"Natural Extra",
  "1":"Ash","11":"Ash Extra","12":"Ash Beige","13":"Cendré Plus","16":"Ash Brown","19":"Violet Ash",
  "2":"Iridescent","21":"Ash Iridescent","22":"Iridescent Extra","24":"Iridescent Beige","29":"Violet Iridescent",
  "3":"Matt","33":"Matt Extra",
  "4":"Beige","42":"Beige Iridescent","46":"Beige Chocolate","48":"Beige Red",
  "5":"Gold","55":"Gold Extra","57":"Gold Copper",
  "6":"Chocolate","63":"Chocolate Matt","65":"Chocolate Gold","67":"Chocolate Copper","68":"Chocolate Red",
  "7":"Copper","76":"Copper Chocolate","77":"Copper Extra",
  "8":"Red","84":"Red Beige","88":"Red Extra",
  "9":"Violet","98":"Violet Red","99":"Violet Extra"
};

const SINGLE_TONE = {
  "0":"Natural","1":"Ash","2":"Iridescent","3":"Matt",
  "4":"Beige","5":"Gold","6":"Chocolate","7":"Copper","8":"Red","9":"Violet"
};

const LEVEL_LABELS = {
  "1":"1 \u00b7 Black","2":"2 \u00b7 Very Dark Brown","3":"3 \u00b7 Dark Brown",
  "4":"4 \u00b7 Medium Brown","5":"5 \u00b7 Light Brown","6":"6 \u00b7 Dark Blonde",
  "7":"7 \u00b7 Medium Blonde","8":"8 \u00b7 Light Blonde",
  "9":"9 \u00b7 Extra Light Blonde","9.5":"9.5 \u00b7 Ultra Light Blonde",
  "specialty":"Specialty"
};

const LINE_LABELS = {
  R:"Igora Royal", V:"Igora Vibrance", C:"Igora Color10",
  H:"Igora Royal Highlifts", SB:"Igora Royal Special Blonde",
  A:"Igora Royal Absolutes", AB:"Igora Royal Absolutes Age Blend",
  SW:"Igora Royal Silver Whites", FL:"Igora Royal Fashion Lights", SP:"Speciality Range"
};

const VIBRANCE_EXCLUSIVE = new Set(["6-23","6-78","7-48","8-19"]);
const VIBRANCE_PASTEL    = new Set([
  "9.5-5","9.5-9","9.5-11","9.5-19","9.5-21","9.5-24","9.5-29","9.5-31","9.5-46","9.5-47","9.5-98",
  "10-5","10-51","10-57","10-91"
]);

const SHADES_RAW = [
  // ── Igora Royal Naturals ──
  {s:"1-0",   lv:"1",   tc:"0",   ln:["R"]},
  {s:"1-1",   lv:"1",   tc:"1",   ln:["R"]},
  {s:"3-0",   lv:"3",   tc:"0",   ln:["R","V"]},
  {s:"4-0",   lv:"4",   tc:"0",   ln:["R","V"]},
  {s:"5-0",   lv:"5",   tc:"0",   ln:["R","V","C"]},
  {s:"5-00",  lv:"5",   tc:"00",  ln:["R","V"]},
  {s:"6-0",   lv:"6",   tc:"0",   ln:["R","V","C"]},
  {s:"6-00",  lv:"6",   tc:"00",  ln:["R","V"]},
  {s:"7-0",   lv:"7",   tc:"0",   ln:["R","V","C"]},
  {s:"7-00",  lv:"7",   tc:"00",  ln:["R","V"]},
  {s:"8-0",   lv:"8",   tc:"0",   ln:["R","V","C"]},
  {s:"8-00",  lv:"8",   tc:"00",  ln:["R","V"]},
  {s:"9-0",   lv:"9",   tc:"0",   ln:["R","V","C"]},
  {s:"9-00",  lv:"9",   tc:"00",  ln:["R","V"]},
  // ── Igora Royal Cendrés & Cools ──
  {s:"4-13",  lv:"4",   tc:"13",  ln:["R"]},
  {s:"5-1",   lv:"5",   tc:"1",   ln:["R","V","C"]},
  {s:"5-16",  lv:"5",   tc:"16",  ln:["R"]},
  {s:"5-21",  lv:"5",   tc:"21",  ln:["R"]},
  {s:"6-1",   lv:"6",   tc:"1",   ln:["R","V","C"]},
  {s:"6-12",  lv:"6",   tc:"12",  ln:["R","V"]},
  {s:"6-16",  lv:"6",   tc:"16",  ln:["R","V"]},
  {s:"7-1",   lv:"7",   tc:"1",   ln:["R","V","C"]},
  {s:"7-21",  lv:"7",   tc:"21",  ln:["R"]},
  {s:"7-24",  lv:"7",   tc:"24",  ln:["R"]},
  {s:"8-1",   lv:"8",   tc:"1",   ln:["R","V","C"]},
  {s:"8-11",  lv:"8",   tc:"11",  ln:["R","V"]},
  {s:"8-21",  lv:"8",   tc:"21",  ln:["R"]},
  {s:"9-1",   lv:"9",   tc:"1",   ln:["R","V","C"]},
  {s:"9-11",  lv:"9",   tc:"11",  ln:["R"]},
  {s:"9-19",  lv:"9",   tc:"19",  ln:["R"]},
  {s:"9-24",  lv:"9",   tc:"24",  ln:["R"]},
  {s:"9.5-1", lv:"9.5", tc:"1",   ln:["R","V"]},
  {s:"9.5-22",lv:"9.5", tc:"22",  ln:["R","V"]},
  // ── Igora Royal Beiges & Golds ──
  {s:"4-5",   lv:"4",   tc:"5",   ln:["R"]},
  {s:"5-4",   lv:"5",   tc:"4",   ln:["R","C"]},
  {s:"5-5",   lv:"5",   tc:"5",   ln:["R","C"]},
  {s:"5-57",  lv:"5",   tc:"57",  ln:["R"]},
  {s:"6-4",   lv:"6",   tc:"4",   ln:["R"]},
  {s:"6-5",   lv:"6",   tc:"5",   ln:["R","C"]},
  {s:"7-4",   lv:"7",   tc:"4",   ln:["R","C"]},
  {s:"7-42",  lv:"7",   tc:"42",  ln:["R"]},
  {s:"7-55",  lv:"7",   tc:"55",  ln:["R","C"]},
  {s:"7-57",  lv:"7",   tc:"57",  ln:["R"]},
  {s:"8-4",   lv:"8",   tc:"4",   ln:["R","C"]},
  {s:"8-55",  lv:"8",   tc:"55",  ln:["R","C"]},
  {s:"9-4",   lv:"9",   tc:"4",   ln:["R","C"]},
  {s:"9-42",  lv:"9",   tc:"42",  ln:["R"]},
  {s:"9-55",  lv:"9",   tc:"55",  ln:["R","C"]},
  {s:"9.5-4", lv:"9.5", tc:"4",   ln:["R","V"]},
  {s:"9.5-49",lv:"9.5", tc:"49",  ln:["R"]},
  // ── Igora Royal Chocolates ──
  {s:"3-65",  lv:"3",   tc:"65",  ln:["R"]},
  {s:"3-68",  lv:"3",   tc:"68",  ln:["R"]},
  {s:"4-6",   lv:"4",   tc:"6",   ln:["R"]},
  {s:"4-46",  lv:"4",   tc:"46",  ln:["R","V"]},
  {s:"4-63",  lv:"4",   tc:"63",  ln:["R"]},
  {s:"4-65",  lv:"4",   tc:"65",  ln:["R","V"]},
  {s:"4-68",  lv:"4",   tc:"68",  ln:["R","V"]},
  {s:"5-6",   lv:"5",   tc:"6",   ln:["R"]},
  {s:"5-63",  lv:"5",   tc:"63",  ln:["R"]},
  {s:"5-65",  lv:"5",   tc:"65",  ln:["R","V","C"]},
  {s:"5-68",  lv:"5",   tc:"68",  ln:["R","V"]},
  {s:"6-6",   lv:"6",   tc:"6",   ln:["R"]},
  {s:"6-46",  lv:"6",   tc:"46",  ln:["R","V"]},
  {s:"6-63",  lv:"6",   tc:"63",  ln:["R"]},
  {s:"6-65",  lv:"6",   tc:"65",  ln:["R","V","C"]},
  {s:"6-68",  lv:"6",   tc:"68",  ln:["R","V"]},
  {s:"7-65",  lv:"7",   tc:"65",  ln:["R","V","C"]},
  {s:"8-65",  lv:"8",   tc:"65",  ln:["R","V","C"]},
  {s:"9-65",  lv:"9",   tc:"65",  ln:["R","C"]},
  // ── Igora Royal Reds & Coppers ──
  {s:"4-88",  lv:"4",   tc:"88",  ln:["R"]},
  {s:"4-99",  lv:"4",   tc:"99",  ln:["R","V"]},
  {s:"5-7",   lv:"5",   tc:"7",   ln:["R"]},
  {s:"5-67",  lv:"5",   tc:"67",  ln:["R","V"]},
  {s:"5-88",  lv:"5",   tc:"88",  ln:["R","V"]},
  {s:"5-99",  lv:"5",   tc:"99",  ln:["R","V"]},
  {s:"6-29",  lv:"6",   tc:"29",  ln:["R"]},
  {s:"6-77",  lv:"6",   tc:"77",  ln:["R","V"]},
  {s:"6-88",  lv:"6",   tc:"88",  ln:["R","V"]},
  {s:"6-99",  lv:"6",   tc:"99",  ln:["R","V"]},
  {s:"7-7",   lv:"7",   tc:"7",   ln:["R"]},
  {s:"7-67",  lv:"7",   tc:"67",  ln:["R"]},
  {s:"7-76",  lv:"7",   tc:"76",  ln:["R"]},
  {s:"7-77",  lv:"7",   tc:"77",  ln:["R","V"]},
  {s:"8-46",  lv:"8",   tc:"46",  ln:["R","V"]},
  {s:"8-77",  lv:"8",   tc:"77",  ln:["R","V"]},
  {s:"8-84",  lv:"8",   tc:"84",  ln:["R"]},
  {s:"9-7",   lv:"9",   tc:"7",   ln:["R"]},
  {s:"9-98",  lv:"9",   tc:"98",  ln:["R"]},
  // ── Igora Royal Highlifts (10-series) ──
  {s:"10-0",  lv:"specialty", tc:"0",  ln:["H"]},
  {s:"10-1",  lv:"specialty", tc:"1",  ln:["H","V"]},
  {s:"10-4",  lv:"specialty", tc:"4",  ln:["H","V"]},
  {s:"10-12", lv:"specialty", tc:"12", ln:["H","V"]},
  {s:"10-14", lv:"specialty", tc:"14", ln:["H"]},
  {s:"10-19", lv:"specialty", tc:"19", ln:["H","V"]},
  {s:"10-21", lv:"specialty", tc:"21", ln:["H"]},
  {s:"10-42", lv:"specialty", tc:"42", ln:["H","V"]},
  {s:"10-46", lv:"specialty", tc:"46", ln:["H"]},
  // ── Igora Royal Special Blonde (12-series) ──
  {s:"12-0",  lv:"specialty", tc:"0",  ln:["SB"]},
  {s:"12-1",  lv:"specialty", tc:"1",  ln:["SB"]},
  {s:"12-2",  lv:"specialty", tc:"2",  ln:["SB"]},
  {s:"12-4",  lv:"specialty", tc:"4",  ln:["SB"]},
  {s:"12-11", lv:"specialty", tc:"11", ln:["SB"]},
  {s:"12-19", lv:"specialty", tc:"19", ln:["SB"]},
  {s:"12-46", lv:"specialty", tc:"46", ln:["SB"]},
  // ── Igora Royal Absolutes ──
  {s:"4-50",  lv:"4",   tc:"50",  ln:["A"]},
  {s:"4-60",  lv:"4",   tc:"60",  ln:["A"]},
  {s:"4-70",  lv:"4",   tc:"70",  ln:["A"]},
  {s:"4-80",  lv:"4",   tc:"80",  ln:["A"]},
  {s:"4-90",  lv:"4",   tc:"90",  ln:["A"]},
  {s:"5-50",  lv:"5",   tc:"50",  ln:["A"]},
  {s:"5-60",  lv:"5",   tc:"60",  ln:["A"]},
  {s:"5-70",  lv:"5",   tc:"70",  ln:["A"]},
  {s:"5-80",  lv:"5",   tc:"80",  ln:["A"]},
  {s:"6-50",  lv:"6",   tc:"50",  ln:["A"]},
  {s:"6-60",  lv:"6",   tc:"60",  ln:["A"]},
  {s:"6-70",  lv:"6",   tc:"70",  ln:["A"]},
  {s:"6-80",  lv:"6",   tc:"80",  ln:["A"]},
  {s:"7-50",  lv:"7",   tc:"50",  ln:["A"]},
  {s:"7-60",  lv:"7",   tc:"60",  ln:["A"]},
  {s:"7-70",  lv:"7",   tc:"70",  ln:["A"]},
  {s:"8-50",  lv:"8",   tc:"50",  ln:["A"]},
  {s:"9-40",  lv:"9",   tc:"40",  ln:["A"]},
  {s:"9-50",  lv:"9",   tc:"50",  ln:["A"]},
  {s:"9-60",  lv:"9",   tc:"60",  ln:["A"]},
  // ── Igora Royal Absolutes Age Blend ──
  {s:"6-07",  lv:"6",   tc:"07",  ln:["AB"]},
  {s:"6-460", lv:"6",   tc:"460", ln:["AB"]},
  {s:"6-580", lv:"6",   tc:"580", ln:["AB"]},
  {s:"7-450", lv:"7",   tc:"450", ln:["AB"]},
  {s:"7-560", lv:"7",   tc:"560", ln:["AB"]},
  {s:"7-710", lv:"7",   tc:"710", ln:["AB"]},
  {s:"8-01",  lv:"8",   tc:"01",  ln:["AB"]},
  {s:"8-07",  lv:"8",   tc:"07",  ln:["AB"]},
  {s:"8-140", lv:"8",   tc:"140", ln:["AB"]},
  {s:"9-560", lv:"9",   tc:"560", ln:["AB"]},
  // ── Igora Royal Silver Whites ──
  {s:"SW: Silver",    lv:"specialty", tc:"", ln:["SW"]},
  {s:"SW: Grey Lilac",lv:"specialty", tc:"", ln:["SW"]},
  {s:"SW: Dove Grey", lv:"specialty", tc:"", ln:["SW"]},
  {s:"SW: Slate Grey",lv:"specialty", tc:"", ln:["SW"]},
  // ── Igora Royal Fashion Lights ──
  {s:"L-00",  lv:"specialty", tc:"00", ln:["FL"]},
  {s:"L-44",  lv:"specialty", tc:"44", ln:["FL"]},
  {s:"L-77",  lv:"specialty", tc:"77", ln:["FL"]},
  {s:"L-88",  lv:"specialty", tc:"88", ln:["FL"]},
  {s:"L-89",  lv:"specialty", tc:"89", ln:["FL"]},
  // ── Igora Vibrance Exclusive ──
  {s:"6-23",  lv:"6",   tc:"23",  ln:["V"]},
  {s:"6-78",  lv:"6",   tc:"78",  ln:["V"]},
  {s:"7-48",  lv:"7",   tc:"48",  ln:["V"]},
  {s:"8-19",  lv:"8",   tc:"19",  ln:["V"]},
  // ── Igora Vibrance Pastel Toners — 9.5-series (V only) ──
  {s:"9.5-5", lv:"9.5", tc:"5",   ln:["V"]},
  {s:"9.5-9", lv:"9.5", tc:"9",   ln:["V"]},
  {s:"9.5-11",lv:"9.5", tc:"11",  ln:["V"]},
  {s:"9.5-19",lv:"9.5", tc:"19",  ln:["V"]},
  {s:"9.5-21",lv:"9.5", tc:"21",  ln:["V"]},
  {s:"9.5-24",lv:"9.5", tc:"24",  ln:["V"]},
  {s:"9.5-29",lv:"9.5", tc:"29",  ln:["V"]},
  {s:"9.5-31",lv:"9.5", tc:"31",  ln:["V"]},
  {s:"9.5-46",lv:"9.5", tc:"46",  ln:["V"]},
  {s:"9.5-47",lv:"9.5", tc:"47",  ln:["V"]},
  {s:"9.5-98",lv:"9.5", tc:"98",  ln:["V"]},
  // ── Igora Vibrance Pastel Toners — 10-series (V only) ──
  {s:"10-5",  lv:"specialty", tc:"5",  ln:["V"]},
  {s:"10-51", lv:"specialty", tc:"51", ln:["V"]},
  {s:"10-57", lv:"specialty", tc:"57", ln:["V"]},
  {s:"10-91", lv:"specialty", tc:"91", ln:["V"]},
  // ── Speciality Range — Clear ──
  {s:"0-00",  lv:"specialty", tc:"00", ln:["SP"]},
  // ── Speciality Range — Neutralisers ──
  {s:"0-11",  lv:"specialty", tc:"11", ln:["SP"]},
  {s:"0-22",  lv:"specialty", tc:"22", ln:["SP"]},
  {s:"0-33",  lv:"specialty", tc:"33", ln:["SP"]},
  // ── Speciality Range — Boosters ──
  {s:"0-55",  lv:"specialty", tc:"55", ln:["SP"]},
  {s:"0-77",  lv:"specialty", tc:"77", ln:["SP"]},
  {s:"0-88",  lv:"specialty", tc:"88", ln:["SP"]},
  {s:"0-89",  lv:"specialty", tc:"89", ln:["SP"]},
  {s:"0-99",  lv:"specialty", tc:"99", ln:["SP"]},
  // ── Speciality Range — Extracts ──
  {s:"D-0",   lv:"specialty", tc:"0",  ln:["SP"]},
  {s:"E-0",   lv:"specialty", tc:"0",  ln:["SP"]},
  {s:"E-1",   lv:"specialty", tc:"1",  ln:["SP"]},
];

function primToneDisplay(tc) {
  if (!tc) return "\u2014";
  if (TONE_MAP[tc]) return tc + " \u00b7 " + TONE_MAP[tc];
  const f = tc[0];
  const name = SINGLE_TONE[f] || "?";
  return f + " \u00b7 " + name + (tc.length > 1 ? " (blend)" : "");
}

function secToneDisplay(tc) {
  if (!tc || tc.length <= 1) return "\u2014";
  if (tc.length === 2) {
    const [a, b] = [tc[0], tc[1]];
    if (a === b) return b + " \u00b7 Extra Intense";
    return b + " \u00b7 " + (SINGLE_TONE[b] || "?");
  }
  return tc.slice(1) + " (Absolutes)";
}

function shadeNotes(shade, ln) {
  if (ln.includes("H"))  return "30vol or 40vol \u00b7 Base 7-8 \u00b7 Never on colored hair \u00b7 1:1 ratio";
  if (ln.includes("SB")) return "30vol or 40vol \u00b7 Base 6-8 \u00b7 1:2 ratio";
  if (ln.includes("AB")) return "30vol \u00b7 1:1 \u00b7 Mature hair \u00b7 Softer double-reflex \u00b7 Flatters mature skin tones";
  if (ln.includes("A"))  return "30vol \u00b7 1:1 \u00b7 Mature hair \u00b7 100% grey coverage \u00b7 Pro-Age Complex";
  if (ln.includes("SW")) return "10vol only \u00b7 1:1 \u00b7 Deposit only \u00b7 White/grey hair";
  if (ln.includes("FL")) return "30 or 40vol \u00b7 1:2 ratio \u00b7 Highlights & lowlights";
  if (shade === "0-00")  return "Clear \u2014 use as gloss or dilute depth \u00b7 With 6vol Activator";
  if (["0-11","0-22","0-33"].includes(shade)) return "Add to any shade \u00b7 L8-9: \u22645% \u00b7 L6-7: \u226415% \u00b7 L1-5: \u226425%";
  if (["0-55","0-77","0-88","0-89","0-99"].includes(shade)) return "Add to any shade to intensify tone";
  if (["D-0","E-0","E-1"].includes(shade)) return "Fashion extract / diluter";
  if (VIBRANCE_EXCLUSIVE.has(shade)) return "6vol Activator Lotion \u00b7 Vibrance exclusive \u00b7 Not available in Royal";
  if (VIBRANCE_PASTEL.has(shade))    return "6vol Activator \u00b7 Pre-lightened hair only \u00b7 Pastel toner";
  const parts = [];
  if (ln.includes("V") && ln.includes("R")) parts.push("Also in Vibrance: 6vol Activator");
  else if (ln.includes("V"))                parts.push("Vibrance: 6vol Activator \u00b7 Demi-permanent \u00b7 5-20 min \u00b7 Ammonia-free");
  if (ln.includes("C")) parts.push("Also in Color10: 20vol \u00b7 10-min");
  if (shade.startsWith("9.5") && ln.includes("R")) parts.push("Pastel toner \u00b7 very light base");
  return parts.join(" \u00b7 ");
}

function renderShadeTable() {
  const tbody = document.getElementById("shade-tbody");
  tbody.innerHTML = SHADES_RAW.map(d => {
    const linesCodes   = d.ln.join(",");
    const linesDisplay = d.ln.map(l => LINE_LABELS[l] || l).join(", ");
    const notes = shadeNotes(d.s, d.ln);
    return `<tr data-shade="${d.s.toLowerCase()}" data-lines="${linesCodes}" data-level="${d.lv}" data-tone="${d.tc}">
      <td class="sc-shade">${d.s}</td>
      <td>${LEVEL_LABELS[d.lv] || d.lv}</td>
      <td>${primToneDisplay(d.tc)}</td>
      <td>${secToneDisplay(d.tc)}</td>
      <td style="font-size:12px">${linesDisplay}</td>
      <td class="sc-note">${notes}</td>
    </tr>`;
  }).join("");
  filterShades();
}

function filterShades() {
  const search = document.getElementById("sc-search").value.toLowerCase();
  const line   = document.getElementById("sc-line").value;
  const level  = document.getElementById("sc-level").value;
  const tone   = document.getElementById("sc-tone").value;

  let visible = 0;
  const rows = document.querySelectorAll("#shade-tbody tr");
  rows.forEach(r => {
    const match =
      (!search || r.dataset.shade.includes(search)) &&
      (!line   || r.dataset.lines.split(",").includes(line)) &&
      (!level  || r.dataset.level === level) &&
      (!tone   || r.dataset.tone === tone);
    r.style.display = match ? "" : "none";
    if (match) visible++;
  });
  document.getElementById("sc-count").textContent =
    "Showing " + visible + " of " + rows.length + " shades";
}

// ── Formula Builder ───────────────────────────────────────────────────────────

async function buildFormula() {
  const currentLevel  = document.getElementById('fb-current-level').value;
  const condition     = document.getElementById('fb-condition').value;
  const grey          = document.getElementById('fb-grey').value;
  const targetLevel   = document.getElementById('fb-target-level').value;
  const targetTone    = document.getElementById('fb-target-tone').value;
  const preferredLine = document.getElementById('fb-line').value;
  const notes         = document.getElementById('fb-notes').value.trim();

  if (!targetLevel || !targetTone) {
    alert('Please select a target level and tone.');
    return;
  }

  const btn = document.getElementById('fb-build-btn');
  btn.disabled = true;

  const resultArea = document.getElementById('fb-result-area');
  resultArea.innerHTML = '<div class="fb-loading">&#9986;&#65039; Generating formula...</div>';
  resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const res = await fetch('/formula', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ currentLevel, condition, grey, targetLevel, targetTone, preferredLine, notes }),
    });
    const data = await res.json();
    if (data.error) {
      resultArea.innerHTML = '<div class="fb-loading">Error: ' + escHtml(data.error) + '</div>';
    } else {
      resultArea.innerHTML = '<div class="fb-result">' + marked.parse(data.formula) + '</div>';
      // Refresh sidebar so the saved formula chat appears
      await updateChatList();
    }
  } catch (e) {
    resultArea.innerHTML = '<div class="fb-loading">Network error — please try again.</div>';
  }

  btn.disabled = false;
}
</script>
</body>
</html>"""


# ── Flask routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/chats", methods=["GET"])
def chats_list():
    return jsonify(list_chats())


@app.route("/chats/new", methods=["POST"])
def chats_new():
    chat = make_chat()
    return jsonify({"id": chat["id"], "title": chat["title"]})


@app.route("/chats/<chat_id>", methods=["GET"])
def chats_get(chat_id):
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Not found"}), 404
    return jsonify(chat)


@app.route("/chats/<chat_id>/message", methods=["POST"])
def chats_message(chat_id):
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    is_first = len(chat["messages"]) == 0
    chat["messages"].append({"role": "user", "content": user_msg})

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=build_system_prompt(),
            messages=chat["messages"],
        )
        reply = resp.content[0].text
        chat["messages"].append({"role": "assistant", "content": reply})

        new_title = None
        if is_first and not chat.get("title"):
            new_title = generate_title(user_msg)
            chat["title"] = new_title

        save_chat(chat)
        threading.Thread(target=extract_memory_bg, args=(chat["messages"],), daemon=True).start()
        return jsonify({"reply": reply, "title": new_title})
    except Exception as e:
        chat["messages"].pop()
        return jsonify({"error": str(e)}), 500


@app.route("/payroll", methods=["GET"])
def payroll_get():
    return jsonify(load_payroll())


@app.route("/payroll", methods=["POST"])
def payroll_post():
    data = request.get_json()
    rows = load_payroll()
    rows.append({
        "date":      data["date"],
        "pay":       float(data.get("pay",  0)),
        "tips":      float(data.get("tips", 0)),
        "logged_at": datetime.now().isoformat(),
    })
    save_payroll(rows)
    return jsonify({"ok": True})


@app.route("/payroll/update", methods=["POST"])
def payroll_update():
    data = request.get_json()
    original_date = data.get("original_date")
    rows = load_payroll()
    updated = False
    for row in rows:
        if row.get("date") == original_date:
            row["date"]      = data["date"]
            row["pay"]       = float(data.get("pay",  0))
            row["tips"]      = float(data.get("tips", 0))
            row["logged_at"] = datetime.now().isoformat()
            updated = True
            break
    if not updated:
        return jsonify({"error": "Entry not found"}), 404
    save_payroll(rows)
    return jsonify({"ok": True})


@app.route("/formula", methods=["POST"])
def formula_build():
    data = request.get_json()
    current_level  = data.get("currentLevel",  "Unknown")
    condition      = data.get("condition",      "Virgin / Natural")
    grey           = data.get("grey",           "No Grey")
    target_level   = data.get("targetLevel",    "")
    target_tone    = data.get("targetTone",     "")
    preferred_line = data.get("preferredLine",  "Let AI decide")
    notes          = data.get("notes",          "").strip()

    if not target_level or not target_tone:
        return jsonify({"error": "Target level and tone are required"}), 400

    user_msg = (
        f"Client Formula Request:\n"
        f"- Current Hair Level: {current_level}\n"
        f"- Hair Condition: {condition}\n"
        f"- Grey Percentage: {grey}\n"
        f"- Target Level: {target_level}\n"
        f"- Target Tone: {target_tone}\n"
        f"- Preferred Line: {preferred_line}"
    )
    if notes:
        user_msg += f"\n- Additional Notes: {notes}"

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=FORMULA_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        formula = resp.content[0].text

        # Auto-save to chats so it appears in the Color Assistant sidebar
        title = f"Formula: {target_level} {target_tone}"
        now = datetime.now()
        chat_id = "formula_" + now.strftime("%Y%m%d_%H%M%S_") + os.urandom(3).hex()
        save_chat({
            "id":         chat_id,
            "title":      title,
            "created_at": now.isoformat(),
            "messages": [
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": formula},
            ],
        })

        return jsonify({"formula": formula})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5002, debug=False)
