# 🤖 Smart Agent — Personal AI Portal

A beautiful, production-ready **Personal AI Agent** built with Flask + LangChain + GPT-4o.  
**Communicates in Desi Gujarati 🇮🇳** with real-time web search and file creation capabilities.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🧠 **AI Model** | OpenAI GPT-4o via LangChain |
| 🔍 **Web Search** | DuckDuckGo Search (no API key needed) |
| 📄 **File Creation** | Secure file generation with user confirmation |
| 💬 **Memory** | `ConversationSummaryBufferMemory` (2000 token context) |
| 🗣️ **Language** | Desi Gujarati — feels like a local friend! |
| 🔐 **Security** | Zero hardcoded keys, path traversal protection |
| 🎨 **UI** | Premium dark-mode ChatGPT-style interface |

---

## 🚀 Quick Start (Local)

### 1. Clone the repo
```bash
git clone https://github.com/1995CT/Smart-Agent.git
cd Smart-Agent
```

### 2. Create virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
# Create .env file (NEVER commit this!)
echo OPENAI_API_KEY=your_openai_api_key_here > .env
echo FLASK_SECRET_KEY=your_random_secret_key_here >> .env
```

### 5. Run the app
```bash
python app.py
```

Open your browser → **http://localhost:5000** 🎉

---

## 🌐 Deploy on Render.com

1. Push this repo to GitHub ✅
2. Go to [render.com](https://render.com) → New → **Web Service**
3. Connect your GitHub repo: `1995CT/Smart-Agent`
4. Set the following:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3.11+
5. Add Environment Variables:
   - `OPENAI_API_KEY` = your key
   - `FLASK_SECRET_KEY` = random string
6. Click **Deploy** → Live in ~2 minutes! 🚀

---

## 🛡️ Security

- ✅ API keys loaded from `.env` only
- ✅ `.env` in `.gitignore` — never committed
- ✅ File creation requires explicit user confirmation (`[A]` or `[B]`)
- ✅ Path traversal attack prevention
- ✅ Critical files blocked from overwrite
- ✅ Session-based memory isolation

---

## 🗂️ Project Structure

```
Smart-Agent/
├── app.py              ← Flask backend + LangChain Agent
├── templates/
│   └── index.html      ← Premium ChatGPT-style UI
├── requirements.txt    ← Python dependencies
├── .gitignore          ← Keeps secrets safe
├── .env.example        ← Template for environment setup
└── README.md           ← This file
```

---

## 📸 Built By

**1995CT** · Powered by GPT-4o · Made with ❤️ in Gujarat 🇮🇳
