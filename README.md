# 🚀 SkillBot – AI-Powered Skill Extraction Chatbot

SkillBot is an interactive chatbot that:
- Extracts skills from free-form text (resume bullets, JD snippets, project descriptions)
- Groups them into categories with confidence scores
- Suggests suitable roles (Backend / Full-Stack / DevOps / Data / AI/RAG)
- Builds a live "Profile So Far" view for the user

It works in two modes:

1. **Fallback Mode (no API key, fully local, free)**
2. **LLM + RAG Mode (OpenAI + Chroma, optional)**

---

## 🧠 High-Level Architecture

- **Frontend**: HTML + CSS + vanilla JS (single-page chat UI)
- **Backend**: FastAPI (Python)
- **Skill Engine**:
  - Smart regex + aliases for local extraction
  - Optional OpenAI LLM + RAG path
- **Vector DB**: Chroma (skills knowledge base)
- **DB**: SQLite (conversation history, skills per turn)
- **Deployment**: Docker (image can run anywhere)

---

## 🐳 Run with Docker (Recommended)

### 1️⃣ Run in Local Fallback Mode (No API Key Needed)

This is the simplest way to try the app — no keys, no billing, no setup.

```bash
docker run -d -p 8000:8000 --name skillbot_test prasadkesavarapu/skillbot:latest

Then open:

http://localhost:8000

The chatbot will:

Extract skills from your messages

Suggest roles

Build your profile in the right-hand panel

All using the local smart engine (no LLM calls).

2️⃣ Run with OpenAI LLM + RAG (Optional)
If you want more natural conversation and richer skill extraction, run:

bash
Copy code
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="sk-******" \
  prasadkes/skillbot:latest

Then:

Open http://localhost:8000

Enable the “LLM Mode (if available)” toggle in the UI

If the key is valid, backend uses:

OpenAI Chat Completions (e.g. gpt-4.1-mini)

Chroma-based retrieval over a skills knowledge base

If the key is missing/invalid/quota exceeded:

Backend automatically falls back to the local engine

User still gets a normal response (no crashes)

🛠 Run from Source (Dev Mode)
Prerequisites
Python 3.10+

Git

Steps
bash
Copy code
git clone https://github.com/PrasadKesavarapu/skillbot.git
cd skillbot
Create and activate virtual environment:

Windows (PowerShell):

powershell
Copy code
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
Mac / Linux:

bash
Copy code
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
Then open:

http://127.0.0.1:8000

Optional: Enable LLM Mode in Dev
Set your key before running uvicorn:

Windows (PowerShell):

powershell
Copy code
$env:OPENAI_API_KEY="sk-xxxx"
uvicorn app.main:app --reload
Mac / Linux:

bash
Copy code
export OPENAI_API_KEY="sk-xxxx"
uvicorn app.main:app --reload

✨ Features
Interactive chat-based UX

Skill extraction from short, messy inputs (e.g. py reactjs aws docker)

Skill metadata:

name

category

confidence

evidence

Role suggestion:

Full-Stack Developer

Backend Engineer

DevOps / Cloud Engineer

Data Engineer / Analyst

LLM / RAG Engineer

Live “Profile So Far”:

Aggregated skills

Detected roles

Can be extended to show JD matches, gaps, etc.

📂 Project Structure
text
Copy code
skillbot/
├── app/
│   ├── main.py          # FastAPI endpoints (chat, profile, etc.)
│   ├── rag.py           # Hybrid LLM + fallback skill engine + RAG hooks
│   ├── models.py        # SQLAlchemy models (ConversationTurn)
│   ├── database.py      # SQLite DB session management
│   ├── data/
│   │   └── skills_knowledge_base.md  # Knowledge base for RAG
│   └── chroma_db/       # Chroma vector store (auto-created)
├── static/
│   ├── index.html       # Chat UI + Profile panel
│   ├── styles.css       # Simple, responsive layout
│   └── script.js        # Frontend logic, calls /api/chat
├── requirements.txt
├── Dockerfile
└── README.md
📈 Future Enhancements / Scaling Plan
This project is designed as a prototype that can be scaled into a production system:

Scalability & Architecture

Move from SQLite → PostgreSQL (managed DB like RDS)

Run multiple FastAPI instances behind a load balancer (e.g. Nginx, AWS ALB)

Extract Chroma into a separate service or use a managed vector DB (Qdrant, Pinecone, etc.)

Add a message queue (e.g. Redis / RabbitMQ) for heavy background tasks

Model & RAG Improvements

Plug in more advanced LLMs (e.g. Azure OpenAI, local models via Ollama)

Enrich the skills knowledge base with job description datasets

Add JD upload + automatic candidate vs JD skills matching

Support resume parsing (PDF/Docx) and full skill extraction from CVs

Multi-User / SaaS

Add authentication and multi-tenant support

Store user profiles, history, and recommended learning paths

Expose REST/GraphQL APIs so other apps can consume the skill engine

Analytics & Reporting

Dashboards for:

Most common skills in a team

Skill gaps vs target roles

Recommended training per employee

Export to Excel / PDF for HR or hiring managers

👤 Author
Prasad Kesavarapu

Role: Software Developer

LinkedIn: www.linkedin.com/in/prasad-kesavarapu-67a0021bb

GitHub: PrasadKesavarapu
