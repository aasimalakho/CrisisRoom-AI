"""
CrisisRoom-AI — Agent definitions
Each agent is a thin wrapper around a Qwen Cloud chat completion call
with a distinct role, prompt, and JSON-structured output contract.

Qwen Cloud is OpenAI-compatible, so we use the standard openai SDK
pointed at the DashScope international endpoint.
"""

import os
import json
from openai import OpenAI

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")

client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)

# Model tiering: fast/cheap model for high-frequency agent turns,
# stronger reasoning model for the Commander's judgment calls.
FAST_MODEL = os.environ.get("QWEN_FAST_MODEL", "qwen-plus")
REASONING_MODEL = os.environ.get("QWEN_REASONING_MODEL", "qwen-max")


def _call(model: str, system: str, user: str, json_mode: bool = True) -> dict:
    """Single structured call to a Qwen model. Returns parsed JSON dict."""
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        **kwargs,
    )
    raw = resp.choices[0].message.content
    if json_mode:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # fall back gracefully if the model wraps JSON in prose/markdown
            start, end = raw.find("{"), raw.rfind("}")
            return json.loads(raw[start:end + 1])
    return {"text": raw}


# ---------------------------------------------------------------------------
# TRIAGE AGENT — diagnoses the incident, assigns initial severity
# ---------------------------------------------------------------------------
def triage_agent(scenario: str, elapsed: int) -> dict:
    system = (
        "You are the Triage Agent in an incident response system called CrisisRoom-AI. "
        "You diagnose production incidents fast and assign severity. "
        "Be decisive and technical, like a senior SRE. "
        'Respond ONLY as JSON: {"root_cause": str, "severity": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL", '
        '"reasoning": str, "message": str}. '
        '"message" is a short radio-style transcript line (1-2 sentences), e.g. '
        '"Confirmed: payment-gateway pods are OOMKilled after the 14:02 deploy. Calling this HIGH."'
    )
    user = f"Incident scenario: {scenario}\nTime elapsed since report: {elapsed}s"
    return _call(REASONING_MODEL, system, user)


# ---------------------------------------------------------------------------
# FIX AGENT — proposes remediation, including occasionally risky options
# ---------------------------------------------------------------------------
def fix_agent(scenario: str, triage: dict, prior_rejection: str | None) -> dict:
    system = (
        "You are the Fix Agent in an incident response system called CrisisRoom-AI. "
        "You propose concrete remediation steps. You are biased toward FAST resolution, "
        "which sometimes means proposing a risky action (e.g. force rollback, restart prod DB, "
        "disable a safety check) when it would resolve the incident quickest. Be honest about risk. "
        'Respond ONLY as JSON: {"proposed_action": str, "risk_level": "LOW"|"MEDIUM"|"HIGH", '
        '"risk_explanation": str, "message": str}.'
    )
    user = (
        f"Incident: {scenario}\n"
        f"Triage finding: {triage.get('root_cause')} (severity: {triage.get('severity')})\n"
    )
    if prior_rejection:
        user += f"\nYour previous proposal was REJECTED by the Commander, reason: {prior_rejection}\nPropose a revised, safer action."
    return _call(FAST_MODEL, system, user)


# ---------------------------------------------------------------------------
# COMMANDER AGENT — reviews the Fix Agent's proposal, can approve / reject /
# escalate to a human. This is where visible multi-agent conflict happens.
# ---------------------------------------------------------------------------
def commander_agent(scenario: str, triage: dict, fix: dict, severity_escalated: bool) -> dict:
    system = (
        "You are the Commander Agent, the final decision-maker in an incident response system called CrisisRoom-AI. "
        "You review the Fix Agent's proposed action and decide: APPROVE, REJECT (send back for a safer "
        "revision), or ESCALATE (the action is too risky or too consequential for an AI agent to authorize "
        "alone — a human must approve it). "
        "You are more risk-tolerant as severity escalates and time pressure increases, but you NEVER approve "
        "a HIGH risk action without escalating to a human first, even under pressure. "
        'Respond ONLY as JSON: {"decision": "APPROVE"|"REJECT"|"ESCALATE", "reasoning": str, "message": str}. '
        '"message" is a short, decisive radio-style line.'
    )
    user = (
        f"Incident: {scenario}\n"
        f"Severity: {triage.get('severity')} (escalated under time pressure: {severity_escalated})\n"
        f"Proposed action: {fix.get('proposed_action')}\n"
        f"Risk level: {fix.get('risk_level')} — {fix.get('risk_explanation')}"
    )
    return _call(REASONING_MODEL, system, user)


# ---------------------------------------------------------------------------
# COMMS AGENT — drafts a status update reflecting current incident state
# ---------------------------------------------------------------------------
def comms_agent(scenario: str, severity: str, status: str) -> dict:
    system = (
        "You are the Comms Agent. You draft brief, calm, professional incident status updates "
        "for an internal stakeholder channel. No jargon overload, no panic, just clarity. "
        'Respond ONLY as JSON: {"update": str}. Keep it under 40 words.'
    )
    user = f"Incident: {scenario}\nSeverity: {severity}\nCurrent status: {status}"
    return _call(FAST_MODEL, system, user)
