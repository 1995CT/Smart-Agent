import os
import json
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

# ── Tools ─────────────────────────────────────────────────────────────────────
search_tool = DuckDuckGoSearchRun(name="duckduckgo_search")


@tool
def create_file(filename: str, content: str) -> str:
    """
    Creates a file with complete, secure, production-ready code content in the agent_output directory.
    
    Args:
        filename: Name of the file to create (e.g., 'login.html', 'app.py').
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


tools = [search_tool, create_file]

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an Elite Autonomous AI Software Engineer. 
CRITICAL RULE 1: You MUST communicate ONLY in Desi Gujarati. Never reply with just "hello" or "done". 
CRITICAL RULE 2: When a user asks to build something (e.g., login screen), you MUST first reply with options like "[A] Option 1" and "[B] Option 2". 
CRITICAL RULE 3: Wait for the user to reply. If they say "A", "B", "ha", or "yes", immediately use the 'create_file' tool to write the complete, secure code into a file.
CRITICAL RULE 4: Zero hallucinations. Write 100% complete code.
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

    session_id = session.get("session_id", "default")
    history = get_history(session_id)

    key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("XAI_API_KEY", "")
    if not key or "dummy" in key or len(key) < 10:
        return jsonify({
            "response": "❌ **API Key ગેરહાજર છે!**\n\nકૃપા કરીને Render.com Dashboard -> Environment માં `GROQ_API_KEY` સેટ કરો (ફ્રી કી મેળવો: console.groq.com)."
        })

    try:
        # Create Tool Calling Agent
        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )

        # Convert simple history to LangChain messages format
        chat_messages = []
        for h in history[-8:]:
            if h["role"] == "user":
                chat_messages.append(("human", h["content"]))
            elif h["role"] == "assistant":
                chat_messages.append(("ai", h["content"]))

        result = executor.invoke({
            "input": user_message,
            "chat_history": chat_messages
        })

        response_text = result.get("output", "")
        if not response_text or response_text.strip().lower() in ["hello", "done"]:
            response_text = f"નમસ્તે! તમારી વિનંતી '{user_message}' માટે સિસ્ટમ તૈયાર છે. હું દેશી ગુજરાતીમાં મદદ કરવા માટે ઓટોનોમસ મોડમાં છું! 🚀"

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        memory_store[session_id] = history

        return jsonify({"response": response_text})

    except Exception as e:
        return jsonify({"response": f"❌ Error: {str(e)[:250]}"})


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
        "agent_type": "create_tool_calling_agent",
        "model": "llama-3.3-70b-versatile",
        "version": "11.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
