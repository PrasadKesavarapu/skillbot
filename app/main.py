import uuid
import datetime as dt
from typing import List, Optional, Dict

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import ConversationTurn
from .rag import analyze_message, get_vectorstore

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Skill Finder Chatbot", version="0.2.0")

# CORS (allow frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in prod, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Pydantic models
# -------------------------

class Skill(BaseModel):
    name: str
    category: Optional[str] = ""
    confidence: Optional[float] = Field(default=0.0)
    evidence: Optional[str] = ""


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    skills: List[Skill]
    timestamp: dt.datetime


class TurnOut(BaseModel):
    user_message: str
    bot_response: str
    skills: List[Skill]
    created_at: dt.datetime


# --- New models for profile endpoint ---

class SkillCount(BaseModel):
    name: str
    category: str
    count: int
    avg_confidence: float


class ProfileResponse(BaseModel):
    session_id: str
    total_turns: int
    total_skills: int
    skills: List[SkillCount]
    suggested_roles: List[str]


# --- Models for match endpoint ---

class MatchRequest(BaseModel):
    candidate_text: str
    job_description: str


class MatchResult(BaseModel):
    match_score: float
    candidate_skills: List[Skill]
    jd_skills: List[Skill]
    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]


# -------------------------
# Startup
# -------------------------

@app.on_event("startup")
def startup_event():
    # Ensure vectorstore is ready on startup (lazy load also works)
    try:
        get_vectorstore()
    except Exception as e:
        print(f"Error initializing vectorstore: {e}")


# -------------------------
# Helper functions
# -------------------------

def infer_roles_from_skill_names(skill_names: List[str]) -> List[str]:
    """Very simple heuristics to infer possible roles from skill names."""
    names = set(skill_names)
    roles: List[str] = []

    if "React" in names and (("FastAPI" in names) or ("Node.js" in names) or ("Express" in names)):
        roles.append("Full-Stack Developer")

    if any(s in names for s in ["FastAPI", "Django", "Node.js", "Express", "REST API"]):
        roles.append("Backend Engineer")

    if any(s in names for s in ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "GitHub Actions"]):
        roles.append("DevOps / Cloud Engineer")

    if any(s in names for s in ["Pandas", "NumPy", "SQL", "PostgreSQL", "MongoDB"]):
        roles.append("Data Engineer / Data Analyst")

    if any(s in names for s in ["LangChain", "ChromaDB"]):
        roles.append("LLM / RAG Engineer")

    # Deduplicate while preserving order
    seen = set()
    unique_roles: List[str] = []
    for r in roles:
        if r not in seen:
            unique_roles.append(r)
            seen.add(r)
    return unique_roles


# -------------------------
# Endpoints
# -------------------------

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = request.session_id or str(uuid.uuid4())

    try:
        reply, skills_list = analyze_message(request.message)
    except Exception as e:
        # Log error and return friendly message
        print(f"Error during LLM/RAG: {e}")
        reply = "Sorry, something went wrong while analyzing your skills. Please try again."
        skills_list = []

    # Normalize skills to Skill model
    skills_objs: List[Skill] = []
    for s in skills_list:
        try:
            skills_objs.append(
                Skill(
                    name=str(s.get("name", "")).strip(),
                    category=str(s.get("category", "")).strip(),
                    confidence=float(s.get("confidence", 0.0)),
                    evidence=str(s.get("evidence", "")).strip(),
                )
            )
        except Exception:
            continue

    # Persist in DB
    db_obj = ConversationTurn(
        session_id=session_id,
        user_message=request.message,
        bot_response=reply,
        skills_json=[s.dict() for s in skills_objs],
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        skills=skills_objs,
        timestamp=db_obj.created_at,
    )


@app.get("/api/conversation/{session_id}", response_model=List[TurnOut])
def get_conversation(session_id: str, db: Session = Depends(get_db)):
    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.session_id == session_id)
        .order_by(ConversationTurn.created_at.asc())
        .all()
    )
    result: List[TurnOut] = []
    for t in turns:
        skills_data = t.skills_json or []
        skills_objs = [Skill(**s) for s in skills_data]
        result.append(
            TurnOut(
                user_message=t.user_message,
                bot_response=t.bot_response,
                skills=skills_objs,
                created_at=t.created_at,
            )
        )
    return result


@app.get("/api/profile/{session_id}", response_model=ProfileResponse)
def get_profile(session_id: str, db: Session = Depends(get_db)):
    """
    Aggregate skills across all turns in this session and infer possible roles.
    """
    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.session_id == session_id)
        .all()
    )
    if not turns:
        raise HTTPException(status_code=404, detail="Session not found")

    skill_stats: Dict[str, Dict] = {}  # key = name

    for t in turns:
        skills = t.skills_json or []
        for s in skills:
            name = str(s.get("name", "")).strip()
            if not name:
                continue
            category = str(s.get("category", "")).strip() or "Skill"
            conf = float(s.get("confidence", 0.0))
            if name not in skill_stats:
                skill_stats[name] = {
                    "name": name,
                    "category": category,
                    "count": 0,
                    "sum_conf": 0.0,
                }
            skill_stats[name]["count"] += 1
            skill_stats[name]["sum_conf"] += conf

    skill_counts: List[SkillCount] = []
    for info in skill_stats.values():
        avg_conf = info["sum_conf"] / max(info["count"], 1)
        skill_counts.append(
            SkillCount(
                name=info["name"],
                category=info["category"],
                count=info["count"],
                avg_confidence=avg_conf,
            )
        )

    # Sort by count desc, then avg_conf desc
    skill_counts.sort(key=lambda s: (s.count, s.avg_confidence), reverse=True)

    suggested_roles = infer_roles_from_skill_names([s.name for s in skill_counts])

    return ProfileResponse(
        session_id=session_id,
        total_turns=len(turns),
        total_skills=len(skill_counts),
        skills=skill_counts,
        suggested_roles=suggested_roles,
    )


@app.post("/api/match", response_model=MatchResult)
def match_skills(request: MatchRequest):
    """
    Compare candidate skills vs job description skills and compute match score.
    """
    if not request.candidate_text.strip() or not request.job_description.strip():
        raise HTTPException(status_code=400, detail="Both candidate_text and job_description are required.")

    # Reuse analyze_message for both texts (LLM or fallback)
    cand_reply, cand_skills_raw = analyze_message(request.candidate_text)
    jd_reply, jd_skills_raw = analyze_message(request.job_description)

    cand_skills = [
        Skill(
            name=str(s.get("name", "")).strip(),
            category=str(s.get("category", "")).strip(),
            confidence=float(s.get("confidence", 0.0)),
            evidence=str(s.get("evidence", "")).strip(),
        )
        for s in cand_skills_raw
        if s.get("name")
    ]

    jd_skills = [
        Skill(
            name=str(s.get("name", "")).strip(),
            category=str(s.get("category", "")).strip(),
            confidence=float(s.get("confidence", 0.0)),
            evidence=str(s.get("evidence", "")).strip(),
        )
        for s in jd_skills_raw
        if s.get("name")
    ]

    cand_set = {s.name.lower() for s in cand_skills}
    jd_set = {s.name.lower() for s in jd_skills}

    matched = sorted({s for s in cand_set & jd_set})
    missing = sorted({s for s in jd_set - cand_set})
    extra = sorted({s for s in cand_set - jd_set})

    match_score = 0.0
    if jd_set:
        match_score = len(matched) / len(jd_set)

    return MatchResult(
        match_score=match_score,
        candidate_skills=cand_skills,
        jd_skills=jd_skills,
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
    )


# Serve static frontend
app.mount(
    "/", StaticFiles(directory="static", html=True), name="static"
)
