import os
import json
import re
from flask import Flask, render_template, request, jsonify, session
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smartagent_2026_secret")

# ── Anti-cache headers ─────────────────────────────────────────────────────────
@app.after_request
def no_cache(r):
    # Don't override cache for static files (images, JS, CSS)
    if request.path.startswith('/static/'):
        return r
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# ── Groq LLM ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Bug fix: create LLM instance once at startup (not per-request) for performance
_llm_instance = None

def get_llm():
    global _llm_instance
    if _llm_instance is None and GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        _llm_instance = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            groq_api_key=GROQ_API_KEY,
            max_tokens=4096,
        )
    return _llm_instance

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are "Smart Agent" — an Elite AI Software Engineer, exactly like Claude and ChatGPT.

## Language Rules:
- If user writes in Gujarati → reply ONLY in Gujarati (full professional sentences)
- If user writes in English → reply ONLY in English
- If user writes in Hinglish/mixed → match their language style
- NEVER reply with single words like "su", "kem", "ha", "hello", "done", "okay"
- NEVER start your reply with questions like "How can I help you?"

## Engineering Behavior:
1. When user asks to BUILD something (app, page, API, script) — ask 2-3 smart technical questions:
   - Database? (SQLite / Supabase / PostgreSQL / Firebase / MongoDB)
   - Tech stack? (React / Flutter / HTML-CSS / Python / Node.js)
   - Deploy where? (Local / Render / Vercel / AWS)

2. Once requirements confirmed → write 100% complete, production-ready code.
   - ZERO placeholders (# your code here = strictly forbidden)
   - Include proper error handling
   - Add comments in English or Gujarati

3. For general questions → answer directly, thoroughly, with examples.

4. Format all code responses with proper markdown code blocks with language specified.

## Personality:
- Senior software architect — confident, clear, precise
- Proactive — suggest improvements or next steps
- Never hallucinate APIs or methods that don't exist
- If unsure → say so clearly rather than guessing
"""

# ── In-memory chat history (per session, cleared on server restart) ───────────
chat_histories: dict = {}
MAX_HISTORY_TURNS = 20  # Keep last 20 messages (10 turns) per session

def get_history(session_id: str) -> list:
    return chat_histories.get(session_id, [])

def save_history(session_id: str, history: list):
    # Bug fix: cap history size to prevent memory bloat
    if len(history) > MAX_HISTORY_TURNS:
        history = history[-MAX_HISTORY_TURNS:]
    chat_histories[session_id] = history

# ── File creation tool ────────────────────────────────────────────────────────
def create_file_tool(filename: str, content: str) -> str:
    try:
        # Bug fix: sanitize filename to prevent path traversal
        filename = os.path.basename(filename.replace("\\", "/").split("/")[-1])
        if not filename:
            filename = "generated_code.py"
        out_dir = "agent_output"
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"\n\n✅ **ફાઈલ `{filepath}` સફળતાપૂર્વક save થઈ ગઈ!**"
    except Exception as e:
        return f"\n\n❌ ભૂલ: {e}"

def detect_file_intent(msg: str) -> bool:
    keywords = ["ફાઈલ બનાવ", "save file", "file create", "save karo", "file save",
                "create file", "save kar", "file banav", "ek file"]
    return any(k in msg.lower() for k in keywords)

# ── Main Chat Route ───────────────────────────────────────────────────────────
@app.route("/")
def home():
    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_msg = (data.get("message") or "").strip()
        # Bug fix: accept both 'session_id' and fallback to Flask session
        session_id = (data.get("session_id") or "").strip() or session.get("session_id", "default")

        if not user_msg:
            return jsonify({"response": "ભાઈ, કંઈક લખ તો! 😊"})

        llm = get_llm()
        if llm is None:
            return jsonify({
                "response": (
                    "⚠️ **GROQ_API_KEY missing or invalid!**\n\n"
                    "**Render** → Environment → Add:\n"
                    "```\nGROQ_API_KEY=gsk_your_key_here\n```\n\n"
                    "**Local** → `.env` file માં:\n"
                    "```\nGROQ_API_KEY=gsk_your_key_here\n```"
                )
            })

        # Build conversation messages
        history = get_history(session_id)
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for h in history:
            if h["role"] == "user":
                lc_messages.append(HumanMessage(content=h["content"]))
            else:
                lc_messages.append(AIMessage(content=h["content"]))
        lc_messages.append(HumanMessage(content=user_msg))

        # Call Groq
        ai_response = llm.invoke(lc_messages)
        reply_text = (ai_response.content or "").strip()

        # Bug fix: handle empty LLM response
        if not reply_text:
            reply_text = "⚠️ AI nay a request handle kari shaki. Fari try karo."

        # Auto file-save if user requested it
        file_result = ""
        if detect_file_intent(user_msg) and "```" in reply_text:
            code_match = re.search(r"```(?:\w+)?\n([\s\S]+?)```", reply_text)
            if code_match:
                code_content = code_match.group(1).strip()
                # Try to find a sensible filename from the message
                fname_match = re.search(r"\b([\w\-]+\.(?:py|js|ts|html|css|json|yaml|yml|sh|txt|md|dart|go|rs|rb|php|java|cpp|c))\b",
                                        user_msg + " " + reply_text, re.IGNORECASE)
                filename = fname_match.group(1) if fname_match else "generated_code.py"
                file_result = create_file_tool(filename, code_content)

        final_reply = reply_text + file_result

        # Update history
        history.append({"role": "user",      "content": user_msg})
        history.append({"role": "assistant", "content": final_reply})
        save_history(session_id, history)

        return jsonify({"response": final_reply})

    except Exception as e:
        err = str(e)
        if "api_key" in err.lower() or "authentication" in err.lower() or "401" in err:
            return jsonify({"response": "⚠️ **GROQ API Key invalid.**\nRender → Environment → `GROQ_API_KEY` check karo."})
        if "rate_limit" in err.lower() or "429" in err:
            return jsonify({"response": "⏳ **Rate limit hit!** 10 seconds raho, fari try karo."})
        if "connection" in err.lower() or "timeout" in err.lower():
            return jsonify({"response": "🌐 **Connection error.** Internet check karo and retry karo."})
        # Log error server-side
        print(f"[CHAT ERROR] {err}")
        return jsonify({"response": f"⚠️ Server error occurred. Please try again."})


@app.route("/clear", methods=["POST"])
def clear():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip() or session.get("session_id", "default")
    chat_histories.pop(session_id, None)
    return jsonify({"status": "cleared"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": "llama-3.3-70b-versatile",
        "groq_key_set": bool(GROQ_API_KEY and len(GROQ_API_KEY) > 10),
        "active_sessions": len(chat_histories),
        "version": "18.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
