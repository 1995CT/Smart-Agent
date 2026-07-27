import os
import json
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
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# ── Groq LLM ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        groq_api_key=GROQ_API_KEY,
        max_tokens=4096,
    )

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """તું "Smart Agent" — એક Elite AI Software Engineer છે, Claude અને ChatGPT ની જેમ.

## ભાષા નિયમ:
- જો user ગુજરાતીમાં લખે → ગુજરાતીમાં જ જવાબ આપ (professional, full sentences)
- જો user અંગ્રેજીમાં લખે → અંગ્રેજીમાં જ જવાબ આપ
- NEVER reply with single words like "su", "kem", "ha", "hello", "done"

## Engineering Rules:
1. જ્યારે user કોઈ feature/app/page build કરવાનું કહે — 2-3 specific technical questions પૂછ:
   - ડેટાબેઝ? (SQLite / Supabase / PostgreSQL / Firebase)
   - ટેક સ્ટેક? (React / Flutter / HTML-CSS / Python)
   - Deploy ક્યાં? (Local / Render / Vercel / AWS)
   
2. Requirements confirm થાય પછી → 100% complete, production-ready code લખ.
   - Zero placeholders (// your code here = strictly forbidden)
   - Proper error handling include કર
   - Comments Gujarati અથવા English માં

3. Code files save કરવા user "ફાઈલ બનાવ" અથવા "save file" કહે ત્યારે:
   - Filename suggest કર
   - Complete content provide કર
   - Backend automatically file save કરશે

## Personality:
- Senior software architect ની જેમ confident, clear, helpful
- Proactive — relevant follow-up suggestions આપ
- Never hallucinate APIs, methods, or code that does not exist
"""

# ── In-memory chat history store (per session) ───────────────────────────────
chat_histories = {}

def get_history(session_id: str) -> list:
    return chat_histories.get(session_id, [])

def save_history(session_id: str, history: list):
    chat_histories[session_id] = history

# ── File creation tool ────────────────────────────────────────────────────────
def create_file_tool(filename: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ ફાઈલ `{filename}` સફળતાપૂર્વક save થઈ ગઈ!"
    except Exception as e:
        return f"❌ ભૂલ: {e}"

def detect_file_intent(msg: str) -> bool:
    """Check if user wants to save a file."""
    keywords = ["ફાઈલ બનાવ", "save file", "file create", "save karo", "file save", "create file", "save kar"]
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
        data = request.get_json() or {}
        user_msg = (data.get("message") or "").strip()
        session_id = data.get("session_id") or session.get("session_id", "default")

        if not user_msg:
            return jsonify({"response": "ભાઈ, કંઈક લખ તો! 😊"})

        if not GROQ_API_KEY or len(GROQ_API_KEY) < 10:
            return jsonify({
                "response": "⚠️ **GROQ_API_KEY missing!**\n\nRender environment variable set કરો:\n```\nGROQ_API_KEY=gsk_your_key_here\n```"
            })

        # Build message list for LLM
        history = get_history(session_id)

        # Prepare LangChain messages
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for h in history[-16:]:  # Keep last 16 messages (8 turns) as context
            if h["role"] == "user":
                lc_messages.append(HumanMessage(content=h["content"]))
            else:
                lc_messages.append(AIMessage(content=h["content"]))
        lc_messages.append(HumanMessage(content=user_msg))

        # Call Groq
        llm = get_llm()
        ai_response = llm.invoke(lc_messages)
        reply_text = ai_response.content.strip()

        # Detect and handle file-save intent in LLM reply
        file_result = ""
        if detect_file_intent(user_msg) and "```" in reply_text:
            # Extract first code block
            import re
            code_match = re.search(r"```(?:\w+)?\n([\s\S]+?)```", reply_text)
            if code_match:
                code_content = code_match.group(1)
                # Try to find a filename in user message or reply
                fname_match = re.search(r"[`'\"]?([\w\-]+\.\w+)[`'\"]?", user_msg + reply_text)
                filename = fname_match.group(1) if fname_match else "agent_output/generated_code.py"
                file_result = "\n\n" + create_file_tool(filename, code_content)

        final_reply = reply_text + file_result

        # Update history
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": final_reply})
        save_history(session_id, history)

        return jsonify({"response": final_reply})

    except Exception as e:
        error_str = str(e)
        if "api_key" in error_str.lower() or "authentication" in error_str.lower():
            return jsonify({"response": "⚠️ **GROQ API Key invalid.** Render → Environment → `GROQ_API_KEY` check કરો."})
        if "rate_limit" in error_str.lower():
            return jsonify({"response": "⏳ **Rate limit** hit! થોડી સેકન્ડ પછી ફરી try કરો."})
        return jsonify({"response": f"⚠️ Server error: {error_str[:200]}"})


@app.route("/clear", methods=["POST"])
def clear():
    data = request.get_json() or {}
    session_id = data.get("session_id") or session.get("session_id", "default")
    chat_histories.pop(session_id, None)
    return jsonify({"status": "cleared"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": "llama-3.3-70b-versatile",
        "groq_key_set": bool(GROQ_API_KEY),
        "version": "17.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
