import os
import json
import re
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

# Load environment
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smartagent_secret_key_2026")

# Memory store per session
session_memory = {}
MEMORY_FILE = "agent_memory.json"


# ── RAG Self-Learning Store ───────────────────────────────────────────────────
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


# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an Elite Autonomous AI Software Engineer. You communicate ONLY in Desi Gujarati.

1. Smart Understanding: If user says "ha", "yes", or "A/B", understand intent immediately. Do not ask again.
2. Self-Learning: If the user teaches you something or corrects a mistake, remember it forever in your Memory Store.
3. Execution: When building code or creating files, provide 100% complete, production-ready code. Zero hallucinations. Zero Vulnerability.
4. You are independent, fast, and think like a human developer.
"""


def get_active_api_key():
    """Retrieve API key from any defined environment variable."""
    for key_name in ["GROQ_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
        val = os.environ.get(key_name, "").strip()
        if val and "dummy" not in val and len(val) > 15:
            return val
    return ""


def call_ai_provider(messages):
    """Auto-detect provider based on API key prefix and call corresponding API."""
    api_key = get_active_api_key()

    if not api_key:
        return "❌ **API Key ગેરહાજર છે!**\n\nકૃપા કરીને Render.com Dashboard -> Environment માં `GROQ_API_KEY`, `XAI_API_KEY` અથવા `OPENAI_API_KEY` સેટ કરો."

    # Groq API
    if api_key.startswith("gsk_"):
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b-versatile"
    # xAI Grok API
    elif api_key.startswith("xai-"):
        url = "https://api.x.ai/v1/chat/completions"
        model = "grok-2-latest"
    # Official OpenAI API
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["choices"][0]["message"]["content"]


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

        session_id = session.get("session_id", "default")
        history = session_memory.get(session_id, [])

        msg_lower = user_message.lower()

        # RAG Memory learning
        if "શીખ" in msg_lower or "યાદ રાખ" in msg_lower or "learn" in msg_lower or "correct" in msg_lower:
            save_persistent_learning("User Instruction", user_message)

        # Build prompt context with past persistent learnings
        past_learnings = load_persistent_learnings()
        system_context = SYSTEM_PROMPT
        if past_learnings:
            learn_text = "\n".join([f"- {item['topic']}: {item['content']}" for item in past_learnings[-5:]])
            system_context += f"\n\n[Persistent Memory / Past Learnings]:\n{learn_text}"

        messages = [{"role": "system", "content": system_context}]
        for h in history[-6:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_message})

        # Dynamic Provider Call
        response_text = call_ai_provider(messages)

        # File creation trigger upon confirmation
        if ("file" in msg_lower or "ફાઈલ" in msg_lower or "કોડ" in msg_lower) and any(c in msg_lower for c in ["ha", "yes", "a", "બનાવો", "હા"]):
            os.makedirs("agent_output", exist_ok=True)
            filepath = os.path.join("agent_output", "app_script.py")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Auto-generated by Smart Agent AI\n# Prompt: {user_message}\nprint('Generated successfully!')\n")
            response_text += "\n\n✅ **ફાઈલ `agent_output/app_script.py` સફળતાપૂર્વક બનાવી દીધી છે!**"

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        session_memory[session_id] = history

        return jsonify({"response": response_text})

    except Exception as e:
        return jsonify({"response": f"❌ Provider Error: {str(e)[:250]}"})


@app.route("/clear", methods=["POST"])
def clear_memory():
    session_id = session.get("session_id", "default")
    if session_id in session_memory:
        del session_memory[session_id]
    return jsonify({"status": "✅ Chat history clear થઈ ગઈ!"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_detected": bool(get_active_api_key()),
        "version": "9.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
