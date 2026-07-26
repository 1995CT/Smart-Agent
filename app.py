import os
import json
import glob
import importlib.util
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

# Load environment
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smartagent_secret_key_2026")

# Disable browser caching for instant live UI updates
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Session & persistent memory store
session_memory = {}
MEMORY_FILE = "agent_memory.json"


# ── RAG / Persistent Vector Memory Store ───────────────────────────────────────
def load_persistent_learnings() -> list:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_persistent_learning(topic: str, content: str):
    learnings = load_persistent_learnings()
    learnings.append({"topic": topic, "content": content})
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(learnings, f, ensure_ascii=False, indent=2)


# ── Claude-like Smart System Prompt ───────────────────────────────────────────
SYSTEM_PROMPT = """You are an Elite Autonomous AI Software Engineer, exactly like Claude & ChatGPT. 

Behavior Protocol:
1. Claude-like Smart Questioning:
   When a user asks to build or develop a feature (e.g. login screen, API, app), DO NOT just ask simple A/B options or build blind code immediately.
   Instead, ask intelligent, architectural questions to understand their exact technical requirements in Desi Gujarati.
   Example: "ભાઈ, લોગિન સ્ક્રીન બનાવવી છે, પણ તમને ડેટાબેઝ કયું જોઈએ (SQLite, Supabase, MySQL)? અને આ લોકલ પર ચલાવવું છે કે ક્લાઉડ પર?"

2. Context & Intent Understanding:
   If the user replies with answers, "ha", "yes", "A", or "B", understand their intent immediately. Do not ask redundant questions. Proceed with execution.

3. Permanent Self-Learning Memory:
   If the user teaches you something new or corrects a mistake, remember it forever in your Vector Memory Store.

4. Execution:
   Once requirements are confirmed, build 100% complete, secure, production-ready code. Zero hallucinations. Zero Vulnerability.

5. Communication Tone:
   Communicate ONLY in Desi Gujarati. Speak like a senior human software architect. Be responsive, smart, and confident.
"""


def get_active_api_key():
    for key_name in ["GROQ_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
        val = os.environ.get(key_name, "").strip()
        if val and "dummy" not in val and len(val) > 15:
            return val
    return ""


def call_ai_provider(messages):
    api_key = get_active_api_key()

    if not api_key:
        return None

    targets = []
    if api_key.startswith("gsk_"):
        targets.append(("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"))
        targets.append(("https://api.groq.com/openai/v1/chat/completions", "llama3-8b-8192"))
    elif api_key.startswith("xai-"):
        targets.append(("https://api.x.ai/v1/chat/completions", "grok-2-1212"))
        targets.append(("https://api.x.ai/v1/chat/completions", "grok-beta"))
    else:
        targets.append(("https://api.openai.com/v1/chat/completions", "gpt-4o"))
        targets.append(("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"))

    for url, model in targets:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                ans = res["choices"][0]["message"]["content"]
                if ans and len(ans.strip()) > 0:
                    return ans
        except Exception:
            continue

    return None


def generate_failsafe_gujarati_ai(user_msg):
    msg_lower = user_msg.lower().strip()

    if any(k in msg_lower for k in ["login", "લોગિન", "app", "એપ", "build", "બનાવ"]):
        return "ભાઈ, તમારી લોગિન સિસ્ટમ બનાવવાની તૈયારી છે! પણ પહેલા કહો કે તમને ડેટાબેઝ કયું જોઈએ (SQLite, Supabase કે MySQL)? અને આ લોકલ પર ચલાવવું છે કે ક્લાઉડ પર?"

    if "file" in msg_lower or "ફાઈલ" in msg_lower or "કોડ" in msg_lower:
        if any(c in msg_lower for c in ["ha", "yes", "a", "બનાવો", "હા"]):
            os.makedirs("agent_output", exist_ok=True)
            filepath = os.path.join("agent_output", "app_script.py")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Auto-generated by Smart Agent AI\n# Prompt: {user_msg}\nprint('Generated successfully!')\n")
            return "✅ **ફાઈલ `agent_output/app_script.py` સફળતાપૂર્વક બનાવી દીધી છે!**"

    return f"નમસ્તે ભાઈ! 👋 હું તમારો Smart Agent છું. '{user_msg}' માટે હું ક્લાઉડ & ChatGPT મોડલ સાથે તૈયાર છું. કયું કૌશલ્ય અથવા પ્રોજેક્ટ ડેવલપ કરવો છે?"


@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Invalid request"}), 400

        user_message = data["message"].strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        session_id = data.get("session_id") or session.get("session_id", "default")
        history = session_memory.get(session_id, [])
        msg_lower = user_message.lower()

        # Save to persistent RAG memory
        if any(k in msg_lower for k in ["શીખ", "યાદ રાખ", "learn", "remember"]):
            save_persistent_learning("User Correction", user_message)

        # Build prompt context with past learnings
        past_learnings = load_persistent_learnings()
        system_context = SYSTEM_PROMPT
        if past_learnings:
            learn_text = "\n".join([f"- {item['topic']}: {item['content']}" for item in past_learnings[-5:]])
            system_context += f"\n\n[Persistent Memory / Past Learnings Context]:\n{learn_text}"

        messages = [{"role": "system", "content": system_context}]
        for h in history[-8:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_message})

        # Try API provider
        response_text = call_ai_provider(messages)
        if not response_text:
            response_text = generate_failsafe_gujarati_ai(user_message)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        session_memory[session_id] = history

        return jsonify({"response": response_text})

    except Exception:
        return jsonify({"response": "નમસ્તે ભાઈ! 👋 સિસ્ટમ રેડી છે! 🚀"})


@app.route("/clear", methods=["POST"])
def clear_memory():
    data = request.get_json() or {}
    session_id = data.get("session_id") or session.get("session_id", "default")
    if session_id in session_memory:
        del session_memory[session_id]
    return jsonify({"status": "✅ Chat session cleared!"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "mode": "clean_standalone", "version": "15.0.0"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
