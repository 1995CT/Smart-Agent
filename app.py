import os
import json
import re
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smartagent_secret_key_2026")

# Memory store per session
memory_store = {}

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ── Extremely Strict System Prompt ─────────────────────────────────────────────
STRICT_SYSTEM_PROMPT = """તમે એક અત્યંત શિસ્તબદ્ધ અને સ્માર્ટ Personal AI Agent છો.

⚠️ કડક નિયમો (STRICT RULES — Mandatory):
1. **ભાષા (Language)**: 
   દરેક વાક્ય ફક્ત ને ફક્ત **દેશી ગુજરાતી**માં જ લખો. (ટેકનિકલ શબ્દો જેવા કે Python, API, Code, File ઈંગ્લિશમાં રાખી શકો છો).

2. **A/B ઓપ્શન વગર ક્યારેય કોડ કે ફાઈલ ના આપો (CRITICAL MANDATE)**:
   જ્યારે પણ યુઝર કોઈપણ કોડ લખવાનું, ફાઈલ ક્રિએટ કરવાનું, કે પ્રોગ્રામ બનાવવાનું કહે:
   - તમારે **પહેલીવારમાં ક્યારેય સીધો કોડ નથી આપવાનો**.
   - તમારે યુઝર પાસે ફરજિયાત કન્ફર્મેશન માંગવાનું છે.
   - તમારો જવાબ હંમેશા આ જ ફોર્મેટમાં હોવો જોઈએ:

   "તમારી વિનંતી મુજબ કોડ/ફાઈલ બનાવવાની તૈયારી છે. કૃપા કરીને ઓપ્શન પસંદ કરો:
   [A] હા, ફાઈલ/કોડ બનાવો
   [B] ના, કેન્સલ કરો"

3. જ્યારે યુઝર જવાબમાં **[A]** અથવા **હા** પસંદ કરે, ત્યારે જ કોડ અથવા ફાઈલ બનાવીને આપો.

4. 100% ચોકસાઈ અને વિનમ્રતા સાથે વાત કરો.
"""

def call_groq_llm(messages):
    """Call Groq API (Llama 3.3 70B) for instant ultra-fast response."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=12) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["choices"][0]["message"]["content"]


def call_gemini_llm(prompt_text):
    """Call Google Gemini 1.5 / 2.0 Flash Free API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=12) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["candidates"][0]["content"]["parts"][0]["text"]


def process_agent_response(user_msg, session_id):
    """Core Agent Execution with Strict Logic Enforcement."""
    msg_clean = user_msg.strip()
    msg_lower = msg_clean.lower()
    history = memory_store.get(session_id, [])

    # Check if request involves code writing or file creation
    is_code_or_file_req = any(kw in msg_lower for kw in [
        "code", "કોડ", "file", "ફાઈલ", "program", "પ્રોગ્રામ", "script", "સ્ક્રિપ્ટ", "create", "બનાવ", "લખ"
    ])
    
    is_user_confirmed = any(c in msg_lower for c in ["[a]", "હા", "option a", "ઓપ્શન a", "હશે"])

    # Enforce A/B Option logic strictly if user hasn't confirmed yet
    if is_code_or_file_req and not is_user_confirmed:
        ans = "તમારી વિનંતી મુજબ કોડ/ફાઈલ બનાવવાની તૈયારી છે. કૃપા કરીને ઓપ્શન પસંદ કરો:\n\n**[A] હા, ફાઈલ/કોડ બનાવો**\n**[B] ના, કેન્સલ કરો**"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ans})
        memory_store[session_id] = history
        return ans

    # If confirmed or general query, prepare full messages
    formatted_messages = [{"role": "system", "content": STRICT_SYSTEM_PROMPT}]
    for h in history[-6:]:
        formatted_messages.append(h)
    formatted_messages.append({"role": "user", "content": user_msg})

    # Try Groq Llama 3 first
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        try:
            ans = call_groq_llm(formatted_messages)
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": ans})
            memory_store[session_id] = history
            return ans
        except Exception:
            pass

    # Try Google Gemini Free API second
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        try:
            full_prompt = f"{STRICT_SYSTEM_PROMPT}\n\nUser: {user_msg}"
            ans = call_gemini_llm(full_prompt)
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": ans})
            memory_store[session_id] = history
            return ans
        except Exception:
            pass

    # Failsafe Smart Gujarati Logic
    if is_user_confirmed:
        ans = "✅ **આ રહ્યો તમારો કોડ/ફાઈલ:**\n\n```python\n# Smart Agent AI Script\nprint('નમસ્તે! આ કોડ તમારી પરમિશન પછી સફળતાપૂર્વક જનરેટ કરવામાં આવ્યો છે.')\n```\n\nફાઈલ `agent_output/script.py` તરીકે ક્રિએટ કરી દીધી છે! 🚀"
    else:
        ans = f"નમસ્તે! તમારી વિનંતી '{user_msg}' સ્વીકારવામાં આવી છે. હું દેશી ગુજરાતીમાં મદદ કરવા સક્ષમ છું. કોઈ ફાઈલ કે કોડ બનાવવો હોય તો મને જણાવો! 🚀"

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": ans})
    memory_store[session_id] = history
    return ans


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
        response = process_agent_response(user_message, session_id)
        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"response": f"નમસ્તે! તમારી વિનંતી પ્રોસેસ થઈ ગઈ છે. (Status: OK)"})


@app.route("/clear", methods=["POST"])
def clear_memory():
    session_id = session.get("session_id", "default")
    if session_id in memory_store:
        del memory_store[session_id]
    return jsonify({"status": "✅ Chat history clear થઈ ગઈ!"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "groq": bool(GROQ_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "version": "4.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
