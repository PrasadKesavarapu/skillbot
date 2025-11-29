import json
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

# -----------------------------------------------------------------------------
# Paths for vector DB and knowledge base
# -----------------------------------------------------------------------------

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
DATA_DIR = Path(__file__).parent / "data"
KB_FILE = DATA_DIR / "skills_knowledge_base.md"

CHROMA_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# OpenAI client (only used when OPENAI_API_KEY is set and use_llm=True)
# -----------------------------------------------------------------------------

_OPENAI_CLIENT: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
    return _OPENAI_CLIENT


# ---------------------------------------------------------------------------
# Smarter fallback skill extractor (no external LLM, fully local)
# ---------------------------------------------------------------------------

SKILL_CONFIG = [
    {
        "name": "Python",
        "category": "Programming Language",
        "aliases": ["python", "py", "python3"],
    },
    {
        "name": "Java",
        "category": "Programming Language",
        "aliases": ["java"],
    },
    {
        "name": "JavaScript",
        "category": "Programming Language",
        "aliases": ["javascript", "js"],
    },
    {
        "name": "TypeScript",
        "category": "Programming Language",
        "aliases": ["typescript", "ts"],
    },
    {
        "name": "SQL",
        "category": "Database / Query",
        "aliases": ["sql", "t-sql", "pl/sql"],
    },
    {
        "name": "React",
        "category": "Frontend Framework",
        "aliases": ["react", "reactjs"],
    },
    {
        "name": "Node.js",
        "category": "Backend Runtime",
        "aliases": ["node", "node.js", "nodejs"],
    },
    {
        "name": "Express",
        "category": "Backend Framework",
        "aliases": ["express", "expressjs"],
    },
    {
        "name": "FastAPI",
        "category": "Backend Framework",
        "aliases": ["fastapi"],
    },
    {
        "name": "Django",
        "category": "Backend Framework",
        "aliases": ["django"],
    },
    {
        "name": "MongoDB",
        "category": "Database",
        "aliases": ["mongodb", "mongo"],
    },
    {
        "name": "PostgreSQL",
        "category": "Database",
        "aliases": ["postgres", "postgresql"],
    },
    {
        "name": "MySQL",
        "category": "Database",
        "aliases": ["mysql"],
    },
    {
        "name": "AWS",
        "category": "Cloud",
        "aliases": ["aws", "amazon web services"],
    },
    {
        "name": "Azure",
        "category": "Cloud",
        "aliases": ["azure"],
    },
    {
        "name": "GCP",
        "category": "Cloud",
        "aliases": ["gcp", "google cloud"],
    },
    {
        "name": "Docker",
        "category": "DevOps / Containerization",
        "aliases": ["docker"],
    },
    {
        "name": "Kubernetes",
        "category": "DevOps / Orchestration",
        "aliases": ["kubernetes", "k8s"],
    },
    {
        "name": "CI/CD",
        "category": "DevOps",
        "aliases": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    },
    {
        "name": "GitHub Actions",
        "category": "DevOps",
        "aliases": ["github actions"],
    },
    {
        "name": "Jenkins",
        "category": "DevOps",
        "aliases": ["jenkins"],
    },
    {
        "name": "Machine Learning",
        "category": "ML / AI",
        "aliases": ["machine learning", "ml", "ml/ai"],
    },
    {
        "name": "Data Science",
        "category": "Data / Analytics",
        "aliases": ["data science", "data scientist"],
    },
    {
        "name": "Pandas",
        "category": "Data / Analytics",
        "aliases": ["pandas"],
    },
    {
        "name": "NumPy",
        "category": "Data / Analytics",
        "aliases": ["numpy", "np"],
    },
    {
        "name": "LangChain",
        "category": "LLM / RAG",
        "aliases": ["langchain"],
    },
    {
        "name": "ChromaDB",
        "category": "Vector Database",
        "aliases": ["chroma", "chromadb"],
    },
]


def fallback_extract_skills(message: str) -> List[Dict]:
    """
    Smarter keyword-based skill extraction:
    - uses aliases (python / py / python3, ml / machine learning)
    - uses regex word boundaries to avoid false matches
    - works even for short, inconsistent inputs like "py reactjs aws docker"
    """
    text = message.lower()
    found: Dict[str, Dict] = {}

    for skill in SKILL_CONFIG:
        name = skill["name"]
        category = skill["category"]
        for alias in skill["aliases"]:
            alias = alias.lower()
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text):
                if name not in found:
                    found[name] = {
                        "name": name,
                        "category": category,
                        "confidence": 0.7,
                        "evidence": alias,
                    }
                break

    return list(found.values())


def fallback_response(message: str, skills: List[Dict]) -> str:
    """
    Friendly, interactive response in fallback mode (no external LLM).
    """
    text = message.strip().lower()

    greetings = {"hi", "hello", "hey", "hii", "hey there", "hola"}
    if not skills and any(g == text for g in greetings):
        return (
            "Hey! 👋 I'm your skill assistant.\n\n"
            "Tell me about your experience or paste a resume bullet, and I'll identify your key skills "
            "and suggest matching roles."
        )

    if not skills:
        return (
            "Thanks for sharing! I didn't catch specific technologies from that message.\n\n"
            "Try mentioning some languages (Python, JavaScript), frameworks (React, FastAPI, Django), "
            "databases (MongoDB, PostgreSQL), or cloud tools (AWS, Docker), and I'll extract skills "
            "and build your profile."
        )

    skill_names = [s["name"] for s in skills]
    skill_list_str = ", ".join(skill_names)

    suggested_roles: List[str] = []
    names = set(skill_names)

    if "React" in names and (("FastAPI" in names) or ("Node.js" in names) or ("Express" in names)):
        suggested_roles.append("Full-Stack Developer")

    if any(s in names for s in ["FastAPI", "Django", "Node.js", "Express", "SQL", "REST API"]):
        suggested_roles.append("Backend Engineer")

    if any(s in names for s in ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "GitHub Actions"]):
        suggested_roles.append("DevOps / Cloud Engineer")

    if any(s in names for s in ["Pandas", "NumPy", "SQL", "PostgreSQL", "MongoDB", "Data Science"]):
        suggested_roles.append("Data Engineer / Data Analyst")

    if any(s in names for s in ["LangChain", "ChromaDB", "Machine Learning"]):
        suggested_roles.append("LLM / RAG Engineer")

    seen = set()
    unique_roles: List[str] = []
    for r in suggested_roles:
        if r not in seen:
            unique_roles.append(r)
            seen.add(r)

    if unique_roles:
        roles_str = ", ".join(unique_roles)
        roles_part = f"From this stack, some good role targets could be: {roles_str}."
    else:
        roles_part = (
            "This combination of skills can map to multiple roles depending on your interests and experience."
        )

    return (
        f"Nice, thanks for the context!\n\n"
        f"I can clearly see these skills in your message: {skill_list_str}.\n"
        f"{roles_part}\n\n"
        "What kind of roles are you aiming for (backend, full-stack, data, DevOps, AI/RAG)? "
        "I can help you map your skills to those roles and suggest what to learn next."
    )


# ---------------------------------------------------------------------------
# Knowledge base + Chroma vector store (for RAG, *lightweight* on Render)
# ---------------------------------------------------------------------------

def ensure_kb_file() -> None:
    """Create a default skills knowledge base file if it does not exist."""
    if KB_FILE.exists():
        return

    KB_FILE.write_text(
        """
# Skills Knowledge Base

## Programming Languages
- Python: backend development, data analysis, scripting, ML.
- JavaScript: frontend development, React, Node.js.
- TypeScript: typed JavaScript for large-scale apps.
- Java: backend services, enterprise apps.
- SQL: data querying, relational databases.

## Frameworks & Libraries
- React: building SPA frontends.
- Node.js & Express: backend APIs.
- FastAPI: high performance async Python APIs.
- Django: full-stack web framework.
- LangChain: LLM apps, RAG, chains.
- Pandas: data analysis in Python.
- NumPy: numerical computing.

## Cloud & DevOps
- AWS: EC2, S3, Lambda, RDS, CloudWatch.
- Azure: App Service, Functions, Cosmos DB.
- GCP: Cloud Run, GKE, BigQuery.
- Docker: containerization.
- Kubernetes: container orchestration.
- CI/CD: GitHub Actions, Jenkins, GitLab CI.

## Databases
- MongoDB: NoSQL document DB.
- PostgreSQL: relational DB.
- MySQL: relational DB.
- SQLite: lightweight embedded DB.
- ChromaDB: vector store for embeddings.

## Other
- REST APIs, GraphQL APIs.
- Microservices.
- Unit testing, integration testing.
- MLOps, model serving.
- Agile / Scrum.
        """.strip(),
        encoding="utf-8",
    )


def build_vectorstore() -> Optional[Chroma]:
    """
    Build or load a Chroma vector store from the skills knowledge base
    using OpenAIEmbeddings.

    IMPORTANT for Render:
    - Only builds if OPENAI_API_KEY is set.
    - Does NOT load any heavy local models, so it fits in 512Mi.
    """
    if not os.getenv("OPENAI_API_KEY"):
        # No key -> don't build vectorstore, run in fallback-only mode.
        return None

    ensure_kb_file()

    embeddings = OpenAIEmbeddings()

    if any(CHROMA_DIR.iterdir()):
        return Chroma(
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR),
        )

    text = KB_FILE.read_text(encoding="utf-8").strip()
    docs = [Document(page_content=text)]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " "],
    )
    split_docs = splitter.split_documents(docs)
    if not split_docs:
        split_docs = docs

    vectorstore = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
    )
    vectorstore.persist()
    return vectorstore


_VECTORSTORE: Optional[Chroma] = None


def get_vectorstore() -> Optional[Chroma]:
    """Return a singleton Chroma vector store instance or None."""
    global _VECTORSTORE
    if _VECTORSTORE is None:
        _VECTORSTORE = build_vectorstore()
    return _VECTORSTORE


# ---------------------------------------------------------------------------
# OpenAI + (optional) RAG path
# ---------------------------------------------------------------------------

def llm_analyze_with_rag(message: str) -> Tuple[str, List[Dict]]:
    """
    Use OpenAI Chat Completions + optional Chroma RAG to analyze the message.
    Returns (assistant_response, skills_list).
    """
    context = ""
    vectorstore = get_vectorstore()
    if vectorstore is not None:
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        docs = retriever.get_relevant_documents(message)
        context = "\n\n".join(d.page_content for d in docs)

    system_prompt = """
You are an AI career and skills assistant that BOTH chats naturally and extracts skills.

Your job for each user message:
1. Read the user message and the skills knowledge base context (if provided).
2. Produce a friendly, concise response that:
   - acknowledges what the user said
   - highlights the key skills you see
   - can suggest job roles, learning paths, or next steps
   - can ask a follow-up question to keep the conversation going.
3. Extract SKILLS from the message (technical and soft skills).

Return a JSON object with exactly these keys:
{
  "assistant_response": string,
  "skills": [
    {
      "name": string,
      "category": string,
      "confidence": number,
      "evidence": string
    }
  ]
}

VERY IMPORTANT:
- Output MUST be VALID JSON ONLY.
- Do NOT include markdown, explanations, or any text outside the JSON.
""".strip()

    user_content = f"[CONTEXT]\n{context}\n\n[USER MESSAGE]\n{message}"

    client = get_openai_client()
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )

    raw = completion.choices[0].message.content

    try:
        data = json.loads(raw)
        assistant_response = data.get("assistant_response", "")
        skills = data.get("skills", [])
        if not isinstance(skills, list):
            skills = []
    except Exception:
        assistant_response = raw
        skills = []

    return assistant_response, skills


# ---------------------------------------------------------------------------
# Main analyze function (hybrid: OpenAI + fallback)
# ---------------------------------------------------------------------------

def analyze_message(message: str, use_llm: bool = False) -> Tuple[str, List[Dict]]:
    """
    Analyze the user message and return:
    - assistant_response: chatbot reply text
    - skills: list of {name, category, confidence, evidence}

    Behavior:
      - If use_llm is True AND OPENAI_API_KEY is set:
          Try OpenAI + (optional) RAG. On any error, fall back to local engine.
      - Otherwise:
          Use local smart fallback engine only.
    """
    if use_llm and os.getenv("OPENAI_API_KEY"):
        try:
            return llm_analyze_with_rag(message)
        except Exception as e:
            print(f"LLM/RAG failed, falling back to local engine: {e}")

    # Fallback-only path (also used when key not set or use_llm=False)
    skills = fallback_extract_skills(message)
    reply = fallback_response(message, skills)
    return reply, skills
