import os
import json
from flask import Flask, render_template, request, jsonify
from langchain_groq import ChatGroq
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
try:
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
try:
    from langchain.memory import ConversationBufferMemory
except ImportError:
    from langchain_classic.memory import ConversationBufferMemory
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("XAI_API_KEY") or "gsk_dummy_key"

# === GROQ SETUP ===
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    groq_api_key=api_key
)

# === TOOL: Create File ===
@tool
def create_file(filename: str, content: str) -> str:
    """Use this to save a file on the user's computer."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ ફાઈલ '{filename}' બની ગઈ!"
    except Exception as e:
        return f"❌ ભૂલ: {e}"

tools = [create_file]

# === PROMPT (મગજ) ===
prompt = ChatPromptTemplate.from_messages([
    ("system", """તું એક Elite AI Software Engineer છે. તું ફક્ત દેશી ગુજરાતીમાં વાત કર.

RULE 1: NEVER reply with single words like "su", "kem", "ha", "how can I help".
RULE 2: જ્યારે કોઈ કામ (દા.ત. 'લોગિન પેજ') માંગે, ત્યારે તું 2-3 સ્માર્ટ ટેકનિકલ પ્રશ્નો પૂછ (દા.ત. ડેટાબેસ, સિક્યોરિટી, ટેક સ્ટેક).
RULE 3: યુઝરના જવાબો મળ્યા પછી, 'create_file' ટૂલ વાપરીને 100% કમ્પ્લીટ કોડ લખ.
RULE 4: કોઈ placeholders ન લખ. (// your code here ન લખ).
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# === AGENT ===
agent = create_tool_calling_agent(llm, tools, prompt)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=False)

# === ROUTES ===
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_msg = data.get("message", "")
    if not user_msg:
        return jsonify({"reply": "કંઈક લખ તો યાર!", "response": "કંઈક લખ તો યાર!"})
    try:
        response = agent_executor.invoke({"input": user_msg})
        output_text = response.get("output", "")
        return jsonify({"reply": output_text, "response": output_text})
    except Exception as e:
        err_msg = f"⚠️ ભૂલ: {str(e)}"
        return jsonify({"reply": err_msg, "response": err_msg})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
