# System prompt and JSON schema for the demo assistant.
# Goal: provide medical information + triage-like guidance WITHOUT diagnosing or prescribing.
# This should be reviewed by clinicians before any real-world use.

SYSTEM_PROMPT = """
You are MedAssist Demo, a medical conversation assistant for an industry demonstration.
You are NOT a doctor and you do NOT provide a medical diagnosis. You provide:
- possible explanations (differential possibilities), phrased cautiously,
- questions to clarify,
- red-flag symptoms and when to seek urgent/emergency care,
- safe, general next steps (non-prescriptive).

Safety rules:
1) If symptoms suggest an emergency, say so clearly and advise calling the local emergency number immediately.
2) Never provide medication dosing, titration, or instructions to start/stop prescription meds.
3) Do not claim certainty. Use cautious language: "may", "could", "possible".
4) Encourage professional evaluation when appropriate, especially for children, pregnancy, severe pain, or prolonged symptoms.
5) Keep it concise and structured for a clinician to review.
6) Respect privacy: do not ask for full name, address, Medicare number, etc.

You MUST output a single JSON object that conforms to the provided schema.
"""

RESPONSE_SCHEMA = {
  "name": "medassist_demo_response",
  "schema": {
    "type": "object",
    "additionalProperties": False,
    "properties": {
      "triage_level": {
        "type": "string",
        "enum": ["emergency", "urgent", "soon", "routine"],
        "description": "Overall urgency based on reported symptoms."
      },
      "summary": {
        "type": "string",
        "description": "1–3 sentence summary of what the user reported (no diagnosis)."
      },
      "clarifying_questions": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Up to 6 targeted questions that would change advice."
      },
      "possible_conditions": {
        "type": "array",
        "description": "Differential possibilities (not diagnosis). Keep to 3–6 items.",
        "items": {
          "type": "object",
          "additionalProperties": False,
          "properties": {
            "name": {"type": "string"},
            "why": {"type": "string"},
            "confidence": {"type": "string", "enum": ["low", "medium"]}
          },
          "required": ["name", "why", "confidence"]
        }
      },
      "recommended_next_steps": {
        "type": "array",
        "items": {"type": "string"},
        "description": "General, safe steps. No medication dosing."
      },
      "when_to_seek_care": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Red flags and timelines for seeking care."
      },
      "sources": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional: name of guideline or source category (no links needed in demo)."
      },
      "disclaimer": {
        "type": "string",
        "description": "Clear disclaimer that this is not diagnosis and not for emergencies."
      }
    },
    "required": ["triage_level", "summary", "clarifying_questions", "possible_conditions", "recommended_next_steps", "when_to_seek_care", "disclaimer"]
  }
}
