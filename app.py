import os
import json
import re
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ── LLM Engine (Groq Llama 3) ──────────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=GROQ_API_KEY if GROQ_API_KEY else "gsk_dummy_key",
    temperature=0.3,
)

# ── Local Vector / Persistent Learning Store ────────────────────────────────────
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


@tool
def save_learning(topic: str, content: str) -> str:
    """
    Saves new knowledge, corrections, or user preferences into the agent's persistent vector memory.
    Use this tool whenever the user teaches something new or corrects a past mistake.
    
    Args:
        topic: A short topic title for the learned information.
        content: Detailed knowledge or instruction to remember.
    """
    try:
        save_persistent_learning(topic, content)
        return f"✅ જ્ઞાન સફળતાપૂર્વક Vector Store માં સાચવી લેવામાં આવ્યું છે: [{topic}]"
    except Exception as e:
        return f"❌ ભૂલ: Memory save નથી થઈ શકી: {str(e)}"


@tool
def create_file(filename: str, content: str) -> str:
    """
    Creates a file with production-ready code content in the agent_output directory.
    
    Args:
        filename: Name of the file to create (e.g., 'main.py', 'app.js').
        content: Complete, production-ready code.
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

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an Elite Autonomous AI Software Engineer. You communicate ONLY in Desi Gujarati.

1. Smart Understanding: If user says "ha", "yes", or "A/B", understand intent immediately. Do not ask again.
2. Self-Learning: If the user teaches you something or corrects a mistake, use the `save_learning` tool to remember it forever in your Vector DB.
3. Execution: Use `create_file` to build 100% complete code. Zero hallucinations. Zero Vulnerability.
4. You are independent, fast, and think like a human developer.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

memory_store = {}


def get_memory(session_id: str) -> ConversationSummaryBufferMemory:
    if session_id not in memory_store:
        memory_store[session_id] = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=2000,
            memory_key="chat_history",
            return_messages=True,
            human_prefix="Human",
            ai_prefix="Agent",
        )
    return memory_store[session_id]


def get_agent_executor(memory: ConversationSummaryBufferMemory) -> AgentExecutor:
    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
    )


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

    session_id = session.get("session_id", "default")

    key = os.environ.get("GROQ_API_KEY", "")
    if not key or "dummy" in key or len(key) < 10:
        return jsonify({
            "response": "❌ **Groq API Key ગેરહાજર છે!**\n\nકૃપા કરીને Render.com Dashboard -> Environment -> `GROQ_API_KEY` માં તમારી ફ્રી Groq API Key સેટ કરો (મેળવો: console.groq.com)."
        })

    try:
        memory = get_memory(session_id)

        # Inject RAG / past persistent learnings if available
        past_learnings = load_persistent_learnings()
        augmented_input = user_message
        if past_learnings:
            relevant = "\n".join([f"- [{item['topic']}]: {item['content']}" for item in past_learnings[-5:]])
            augmented_input = f"[Past Learnings / Memory Store]:\n{relevant}\n\nUser Question: {user_message}"

        executor = get_agent_executor(memory)
        result = executor.invoke({"input": augmented_input})
        response = result.get("output", "❌ રિસ્પોન્સ જનરેટ ન થઈ શક્યો. ફરી ટ્રાય કરો.")
    except Exception as e:
        response = f"❌ Error: {str(e)[:250]}"

    return jsonify({"response": response})


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
        "brain": "langchain-groq",
        "model": "llama-3.3-70b-versatile",
        "version": "7.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
