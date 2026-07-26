import os
import json
import glob
import importlib.util
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("XAI_API_KEY", "")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ── LLM Engine (Groq Llama-3.3-70b-versatile) ──────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=GROQ_API_KEY if GROQ_API_KEY else "gsk_dummy_key",
    temperature=0.3,
)

# ── RAG / Persistent Vector Memory Store ───────────────────────────────────────
MEMORY_FILE = "agent_memory.json"


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


# ── Built-in Tools ────────────────────────────────────────────────────────────
@tool
def save_learning(topic: str, content: str) -> str:
    """
    Saves new knowledge, user corrections, or project preferences into persistent vector memory.
    Use this tool whenever the user teaches something new or corrects a past mistake.
    """
    try:
        save_persistent_learning(topic, content)
        return f"✅ જ્ઞાન સફળતાપૂર્વક કાયમી Vector DB મેમરીમાં સેવ થઈ ગયું છે: [{topic}]"
    except Exception as e:
        return f"❌ ભૂલ: Memory save નથી થઈ શકી: {str(e)}"


@tool
def create_file(filename: str, content: str) -> str:
    """
    Creates a file with complete, secure, production-ready code content in the agent_output directory.
    """
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        return "❌ ભૂલ: ખોટું file નામ."

    blocked = [".env", "app.py", "requirements.txt", ".gitignore"]
    if safe_filename in blocked:
        return f"❌ સુરક્ષા: '{safe_filename}' file overwrite કરવાની રજા નથી."

    output_dir = "agent_output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, safe_filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ File '{safe_filename}' સફળતાપૂર્વક '{output_dir}/' માં create થઈ ગઈ!"
    except Exception as e:
        return f"❌ ભૂલ: File create ના થઈ: {str(e)}"


search_tool = DuckDuckGoSearchRun(name="duckduckgo_search")
tools = [search_tool, create_file, save_learning]

# ── Dynamic Plugin Loader (ChatGPT Style) ──────────────────────────────────────
def load_dynamic_plugins():
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_dir):
        return

    plugin_files = glob.glob(os.path.join(plugins_dir, "*.py"))
    for p_file in plugin_files:
        if os.path.basename(p_file).startswith("__"):
            continue
        module_name = f"plugins.{os.path.basename(p_file)[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, p_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                # Register functions decorated with LangChain @tool
                if hasattr(attr, "name") and hasattr(attr, "description") and callable(attr) and attr not in tools:
                    tools.append(attr)
        except Exception:
            pass


load_dynamic_plugins()

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
   If the user teaches you something new or corrects a mistake, use the `save_learning` tool to store it into persistent Vector Memory forever.

4. Execution:
   Once requirements are confirmed, use the `create_file` tool to build 100% complete, secure, production-ready code. Zero hallucinations.

5. Communication Tone:
   Communicate ONLY in Desi Gujarati. Speak like a senior human software architect. Be responsive, smart, and confident.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

memory_store = {}


def get_history(session_id: str) -> list:
    if session_id not in memory_store:
        memory_store[session_id] = []
    return memory_store[session_id]


@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Invalid request"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    session_id = data.get("session_id") or session.get("session_id", "default")
    history = get_history(session_id)

    key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("XAI_API_KEY", "")
    if not key or "dummy" in key or len(key) < 10:
        return jsonify({
            "response": "❌ **API Key ગેરહાજર છે!**\n\nકૃપા કરીને Render.com Dashboard -> Environment માં `GROQ_API_KEY` સેટ કરો (ફ્રી કી મેળવો: console.groq.com)."
        })

    try:
        # Load permanent learnings into prompt
        past_learnings = load_persistent_learnings()
        augmented_message = user_message
        if past_learnings:
            learned_str = "\n".join([f"- {item['topic']}: {item['content']}" for item in past_learnings[-6:]])
            augmented_message = f"[Persistent Memory / Past Learnings Context]:\n{learned_str}\n\n[User Input]: {user_message}"

        # Create agent with dynamically loaded plugin tools
        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )

        chat_messages = []
        for h in history[-8:]:
            if h["role"] == "user":
                chat_messages.append(("human", h["content"]))
            elif h["role"] == "assistant":
                chat_messages.append(("ai", h["content"]))

        result = executor.invoke({
            "input": augmented_message,
            "chat_history": chat_messages
        })

        response_text = result.get("output", "")
        if not response_text or response_text.strip().lower() in ["hello", "done"]:
            response_text = f"નમસ્તે ભાઈ! તમારી વિનંતી '{user_message}' માટે હું ક્લાઉડ & ChatGPT મોડલ સાથે તૈયાર છું. કયું કૌશલ્ય અથવા પ્રોજેક્ટ ડેવલપ કરવો છે?"

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        memory_store[session_id] = history

        return jsonify({"response": response_text})

    except Exception as e:
        return jsonify({"response": f"❌ Error: {str(e)[:250]}"})


@app.route("/clear", methods=["POST"])
def clear_memory():
    data = request.get_json() or {}
    session_id = data.get("session_id") or session.get("session_id", "default")
    if session_id in memory_store:
        del memory_store[session_id]
    return jsonify({"status": "✅ Chat session cleared!"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "agent_type": "Claude-Style Smart Architecture Agent",
        "plugins_loaded": len(tools) - 3,
        "version": "12.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
