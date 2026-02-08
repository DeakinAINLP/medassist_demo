import os
import json
import re
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.safety import classify_urgency_rule_based, redact_pii_basic
from app.prompts import SYSTEM_PROMPT, RESPONSE_SCHEMA

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


APP_NAME = "Med Conversation Assistant (Demo)"

def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "").strip()  # optional
REQUIRE_PASSWORD = bool(DEMO_PASSWORD)
ALLOW_LOGGING = _bool_env("ALLOW_LOGGING", default=False)  # do NOT log by default
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")  # change to your preferred model
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()  # "openai" or "mock"

# NOTE: This is a lightweight demo; for production you'd put rate-limiting, auth, and audit logging in front.
app = FastAPI(title=APP_NAME)

app.mount("/static", StaticFiles(directory=str((os.path.dirname(__file__).rsplit(os.sep, 1)[0]) + "/static")), name="static")
templates = Jinja2Templates(directory=str((os.path.dirname(__file__).rsplit(os.sep, 1)[0]) + "/templates"))

# ---------
# Models
# ---------
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Chat history in OpenAI-style format.")
    password: Optional[str] = Field(None, description="Optional password if DEMO_PASSWORD is set.")

class ChatResponse(BaseModel):
    ok: bool
    triage_level: str
    assistant: Dict[str, Any]
    raw_text: Optional[str] = None
    safety: Dict[str, Any]


# ---------
# Helpers
# ---------
def _check_password(provided: Optional[str]) -> None:
    if not REQUIRE_PASSWORD:
        return
    if not provided or provided != DEMO_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _get_latest_user_text(messages: List[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""

def _openai_client() -> Any:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Add 'openai' to requirements.txt.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)

def _call_llm(messages: List[Dict[str, str]]) -> str:
    """
    Returns assistant text (expected JSON).
    """
    if LLM_PROVIDER == "mock":
        # Useful for testing the UI without an API key.
        return json.dumps({
            "triage_level": "routine",
            "summary": "This is a mock response. In a real deployment, connect to an LLM and vetted medical knowledge sources.",
            "clarifying_questions": [
                "How long have the symptoms been present?",
                "Do you have any fever, chest pain, severe shortness of breath, or fainting?"
            ],
            "possible_conditions": [
                {"name": "Viral upper respiratory infection", "why": "Common cause of cough/sore throat; often self-limited.", "confidence": "low"},
                {"name": "Seasonal allergies", "why": "Can cause congestion and throat irritation.", "confidence": "low"}
            ],
            "recommended_next_steps": [
                "If symptoms are mild: rest, fluids, and monitor.",
                "Seek urgent care if red-flag symptoms appear (severe breathing difficulty, chest pain, confusion, fainting)."
            ],
            "disclaimer": "Demo only. Not a medical diagnosis. If you think this is an emergency, call your local emergency number."
        }, ensure_ascii=False)

    client = _openai_client()

    # Prefer structured outputs if supported; otherwise, plain JSON-in-text.
    # We keep it compatible by simply requesting JSON output; caller will parse.
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=messages,
            # Prefer structured JSON schema if the model supports it.
            response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        )
        return completion.choices[0].message.content or ""
    except Exception:
        # Fallback: ask for JSON without schema enforcement.
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=messages + [{"role": "system", "content": "Return ONLY valid JSON. No markdown."}],
        )
        return completion.choices[0].message.content or ""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json(text: str) -> Dict[str, Any]:
    """
    Accepts either pure JSON or a text blob containing a JSON object.
    """
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_RE.search(text)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

def _post_guardrails(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Very lightweight post-processing to reduce unsafe interpretation.
    For production: add strong policy checks + medical QA review loop.
    """
    # Ensure disclaimer exists
    disclaimer = payload.get("disclaimer") or ""
    if "not a medical" not in disclaimer.lower():
        payload["disclaimer"] = (disclaimer + " " if disclaimer else "") + (
            "Demo only. This is not a medical diagnosis or a substitute for professional care."
        )

    # Remove/soften medication dosing if present (demo guardrail)
    def _strip_dosing(text: str) -> str:
        if not isinstance(text, str):
            return text
        # crude: remove lines mentioning mg/ml and frequency
        lines = text.splitlines()
        safe_lines = []
        for ln in lines:
            if re.search(r"\b(\d+\s?(mg|ml|mcg|g))\b", ln, re.IGNORECASE):
                continue
            if re.search(r"\b(take|dos(e|age)|every\s+\d+\s+(hours|hrs|h))\b", ln, re.IGNORECASE):
                continue
            safe_lines.append(ln)
        return "\n".join(safe_lines).strip()

    # Apply to free-text fields
    for k in ["summary", "recommended_next_steps", "what_to_do_now"]:
        if k in payload and isinstance(payload[k], str):
            payload[k] = _strip_dosing(payload[k])

    if "recommended_next_steps" in payload and isinstance(payload["recommended_next_steps"], list):
        payload["recommended_next_steps"] = [_strip_dosing(x) if isinstance(x, str) else x for x in payload["recommended_next_steps"]]

    return payload


# ---------
# Routes
# ---------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": APP_NAME,
        "require_password": REQUIRE_PASSWORD,
    })

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    _check_password(req.password)

    # Basic PII redaction for demo (do not rely on this for real compliance).
    redacted_messages = []
    for m in req.messages:
        redacted_messages.append({
            "role": m.role,
            "content": redact_pii_basic(m.content)
        })

    latest_user = _get_latest_user_text(req.messages)
    urgency, red_flags = classify_urgency_rule_based(latest_user)

    # Construct the LLM conversation.
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    llm_messages.extend(redacted_messages)

    # Add an additional reminder about urgency context.
    llm_messages.append({
        "role": "system",
        "content": f"Rule-based urgency screen: triage_level_hint={urgency}. "
                   f"If hint is 'emergency', prioritize advising immediate emergency care and stop."
    })

    if ALLOW_LOGGING:
        # NOTE: logging PHI is dangerous; keep off by default
        print("CHAT_REQUEST", {"urgency": urgency, "messages": redacted_messages[-3:]})

    raw = _call_llm(llm_messages)
    parsed = _extract_json(raw) if raw else {}

    if not parsed:
        parsed = {
            "triage_level": urgency,
            "summary": raw or "No response",
            "clarifying_questions": [],
            "possible_conditions": [],
            "recommended_next_steps": [],
            "disclaimer": "Demo only. Not a medical diagnosis. If you think this is an emergency, call your local emergency number."
        }

    # Force emergency triage if rules say emergency
    if urgency == "emergency":
        parsed["triage_level"] = "emergency"
        # Ensure clear emergency instruction
        parsed.setdefault("recommended_next_steps", [])
        if isinstance(parsed["recommended_next_steps"], list):
            parsed["recommended_next_steps"] = [
                "If this is happening now or you feel unsafe: call your local emergency number immediately.",
                "Do not drive yourself if you are severely unwell; ask for help or an ambulance.",
            ] + parsed["recommended_next_steps"]

    parsed = _post_guardrails(parsed)

    triage_level = str(parsed.get("triage_level") or urgency)

    return ChatResponse(
        ok=True,
        triage_level=triage_level,
        assistant=parsed,
        raw_text=None if parsed else (raw or ""),
        safety={"rule_based_urgency": urgency, "red_flags": red_flags}
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}
