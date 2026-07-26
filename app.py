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

# ─── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError(
        "❌ OPENAI_API_KEY environment variable not set. "
        "Please create a .env file with: OPENAI_API_KEY=your_key_here"
    )

# ─── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# ─── LLM ───────────────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    openai_api_key=OPENAI_API_KEY,
    streaming=False,
)

# ─── Tools ─────────────────────────────────────────────────────────────────────
search_tool = DuckDuckGoSearchRun(name="duckduckgo_search")


@tool
def create_file(filename: str, content: str) -> str:
    """
    Creates a file with the given filename and content in the current directory.
    Always ask the user for confirmation (Option A or B) before calling this tool.
    The agent MUST NOT call this tool without explicit user approval.
    
    Args:
        filename: Name of the file to create (e.g., 'hello.py').
        content: The text content to write into the file.
    
    Returns:
        A success or error message in Gujarati.
    """
    # Security: Prevent path traversal attacks
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        return "❌ ભૂલ: ખોટું file નામ. File create નથી થઈ."

    # Prevent overwriting critical files
    blocked = [".env", "app.py", "requirements.txt", ".gitignore"]
    if safe_filename in blocked:
        return f"❌ સુરક્ષા: '{safe_filename}' file ને overwrite કરવાની permission નથી."

    output_dir = "agent_output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, safe_filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ File '{safe_filename}' સફળતાપૂર્વક '{output_dir}/' ફોલ્ડરમાં create થઈ ગઈ!"
    except Exception as e:
        return f"❌ ભૂલ: File create નહી થઈ. Error: {str(e)}"


tools = [search_tool, create_file]

# ─── System Prompt (Desi Gujarati) ─────────────────────────────────────────────
SYSTEM_PROMPT = """તમે એક Expert AI Agent છો — smart, helpful, અને trustworthy.

🗣️ ભાષા: હંમેશા **Desi Gujarati** માં જ communicate કરો. 
   (Technical terms જેમ કે Python, API, file, etc. English માં રાખો.)

🔧 Tools:
- **duckduckgo_search**: Real-time internet search.
- **create_file**: User ની permission પછી જ file create કરો.

⚠️ STRICT RULES — Zero Hallucinations:
1. **File create કરતાં પહેલાં** હંમેશા user ને options આપો:
   "[A] હા, file create કરો  [B] ના, cancel કરો"
   User [A] select કરે ત્યારે જ create_file tool call કરો.

2. **ક્યારેય** API keys, passwords, secrets hardcode ન કરો.

3. **ક્યારેય** user ની explicit permission વગર files overwrite ન કરો.

4. Search results genuine facts પર based છે — guess ન કરો.

5. જો ખબર ન હોય, સ્પષ્ટ કહો: "મને ખ્યાલ નથી, search કરીને confirm કરું?"

6. Professional, friendly, અને concise responses આપો.

🎯 Your Mission: User ના દરેક task ને accurately, securely, અને helpfully execute કરો.
"""

# ─── Prompt Template ───────────────────────────────────────────────────────────
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# ─── Per-session memory store ──────────────────────────────────────────────────
# We keep a dict of session_id -> memory for multi-user support
memory_store: dict[str, ConversationSummaryBufferMemory] = {}


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


# ─── Routes ────────────────────────────────────────────────────────────────────
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

    try:
        memory = get_memory(session_id)
        executor = get_agent_executor(memory)
        result = executor.invoke({"input": user_message})
        response = result.get("output", "❌ Response generate ન થઈ. ફરી try કરો.")
    except Exception as e:
        response = f"❌ System error: {str(e)[:200]}"

    return jsonify({"response": response})


@app.route("/clear", methods=["POST"])
def clear_memory():
    session_id = session.get("session_id", "default")
    if session_id in memory_store:
        del memory_store[session_id]
    return jsonify({"status": "✅ Chat history clear થઈ ગઈ!"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": "gpt-4o", "version": "1.0.0"})


# ─── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
