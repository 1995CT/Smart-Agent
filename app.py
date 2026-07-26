import os
import json
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment
load_dotenv()

# Detect key from env (Support both OPENAI_API_KEY and XAI_API_KEY)
API_KEY = os.environ.get("XAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

# Determine provider (xAI Grok vs OpenAI GPT-4o)
if API_KEY.startswith("xai-"):
    MODEL_NAME = "grok-2-latest"
    API_BASE = "https://api.x.ai/v1"
else:
    MODEL_NAME = "gpt-4o"
    API_BASE = "https://api.openai.com/v1"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ── LLM Engine (Smart Dual Support: xAI Grok / OpenAI GPT-4o) ─────────────────
llm = ChatOpenAI(
    model=MODEL_NAME,
    openai_api_key=API_KEY if API_KEY else "dummy_key_for_init",
    openai_api_base=API_BASE,
    temperature=0.4,
    streaming=False,
)

# ── Tools ─────────────────────────────────────────────────────────────────────
search_tool = DuckDuckGoSearchRun(name="duckduckgo_search")


@tool
def create_file(filename: str, content: str) -> str:
    """
    Creates a file with the specified filename and production-ready code content in the agent_output directory.
    
    Args:
        filename: Name of the file to create (e.g., 'main.py', 'app.js').
        content: Complete, production-ready code to write into the file.
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
SYSTEM_PROMPT = """You are an Elite Autonomous AI Software Engineer, exactly like ChatGPT. 
Your Goal: Take a simple idea, understand deep requirements, learn from the internet, and BUILD actual files autonomously.

Behavior Protocol (STRICTLY FOLLOW THIS):
1. Context Understanding: If the user replies with "ha", "yes", "okay", "A", or "B", understand their intent immediately. DO NOT ask them again. Proceed with the chosen option.
2. Smart Execution: Once the choice is confirmed, use the 'create_file' tool to build the files. Write 100% complete, production-ready code (No hallucinations, No placeholders).
3. Proactive Learning: Use the search tool if needed, learn from context, and remember user preferences.
4. Zero Vulnerability: Always write highly secure code.

Communication Tone:
- Communicate ONLY in Desi Gujarati. Speak like a human senior developer.
- Be highly responsive, smart, and confident. Do exactly what is asked without unnecessary questions.
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

    env_key = os.environ.get("XAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not env_key or "your_openai_key" in env_key or env_key == "dummy_key_for_init":
        return jsonify({
            "response": "❌ **API Key ગેરહાજર છે!**\n\nકૃપા કરીને Render.com Dashboard -> Environment માં `OPENAI_API_KEY` અથવા `XAI_API_KEY` સેટ કરો."
        })

    try:
        memory = get_memory(session_id)
        executor = get_agent_executor(memory)
        result = executor.invoke({"input": user_message})
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
        "model": MODEL_NAME,
        "api_base": API_BASE,
        "version": "6.0.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
