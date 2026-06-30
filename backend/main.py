"""
CrisisRoom-AI — Orchestration + API
Streams a live multi-agent incident response over Server-Sent Events (SSE).
Includes a human-in-the-loop checkpoint: when the Commander escalates a
HIGH-risk action, the simulation pauses until a human approves/denies it
via POST /incidents/{id}/approve.
"""

import asyncio
import json
import time
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import triage_agent, fix_agent, commander_agent, comms_agent

app = FastAPI(title="CrisisRoom-AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of pending human approvals: incident_id -> asyncio.Future
PENDING_APPROVALS: dict[str, asyncio.Future] = {}

SCENARIOS = {
    "payment-outage": "Payment API is returning 500s for ~40% of checkout requests. Started 6 minutes ago, right after a deploy.",
    "db-latency": "Primary database read latency has spiked from 20ms to 1800ms. Connection pool is near exhaustion.",
    "security-breach": "Anomalous admin-level API calls detected from an unrecognized IP range, originating 3 minutes ago.",
}


class ApprovalRequest(BaseModel):
    approved: bool
    note: Optional[str] = None


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_incident(incident_id: str, scenario_key: str):
    scenario = SCENARIOS.get(scenario_key, scenario_key)
    start = time.time()
    severity_escalated = False
    max_rounds = 3

    yield sse("incident_start", {"scenario": scenario, "incident_id": incident_id})
    await asyncio.sleep(0.3)

    # --- Triage ---
    elapsed = int(time.time() - start)
    triage = await asyncio.to_thread(triage_agent, scenario, elapsed)
    yield sse("agent_turn", {"agent": "triage", "elapsed": elapsed, **triage})
    await asyncio.sleep(0.3)

    severity = triage.get("severity", "MEDIUM")
    prior_rejection = None
    resolved = False

    for round_num in range(1, max_rounds + 1):
        elapsed = int(time.time() - start)
        # escalate severity under time pressure
        if elapsed > 25 and not severity_escalated and severity != "CRITICAL":
            severity_escalated = True
            order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            severity = order[min(order.index(severity) + 1, 3)]
            yield sse("severity_escalation", {"new_severity": severity, "elapsed": elapsed})
            await asyncio.sleep(0.3)

        # --- Fix proposal ---
        fix = await asyncio.to_thread(fix_agent, scenario, triage, prior_rejection)
        yield sse("agent_turn", {"agent": "fix", "round": round_num, "elapsed": elapsed, **fix})
        await asyncio.sleep(0.3)

        # --- Commander review ---
        decision = await asyncio.to_thread(commander_agent, scenario, triage, fix, severity_escalated)
        yield sse("agent_turn", {"agent": "commander", "round": round_num, "elapsed": elapsed, **decision})
        await asyncio.sleep(0.3)

        if decision["decision"] == "APPROVE":
            resolved = True
            break
        elif decision["decision"] == "REJECT":
            prior_rejection = decision.get("reasoning", "too risky")
            continue
        elif decision["decision"] == "ESCALATE":
            # Human-in-the-loop checkpoint
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            PENDING_APPROVALS[incident_id] = fut
            yield sse("human_approval_required", {
                "proposed_action": fix.get("proposed_action"),
                "risk_explanation": fix.get("risk_explanation"),
                "commander_reasoning": decision.get("reasoning"),
            })
            approved = await fut  # blocks until POST /approve resolves it
            del PENDING_APPROVALS[incident_id]

            if approved:
                yield sse("human_decision", {"approved": True})
                resolved = True
            else:
                yield sse("human_decision", {"approved": False})
                prior_rejection = "Human operator denied this action — find a less risky path."
                continue
            break

    # --- Comms update + resolution ---
    status = "resolved" if resolved else "unresolved — manual handoff required"
    comms = await asyncio.to_thread(comms_agent, scenario, severity, status)
    yield sse("agent_turn", {"agent": "comms", **comms})

    total_elapsed = int(time.time() - start)
    yield sse("incident_end", {
        "resolved": resolved,
        "final_severity": severity,
        "total_seconds": total_elapsed,
    })


@app.get("/scenarios")
def list_scenarios():
    return SCENARIOS


@app.get("/incidents/start")
async def start_incident(scenario: str = "payment-outage"):
    incident_id = str(uuid.uuid4())[:8]
    return StreamingResponse(
        run_incident(incident_id, scenario),
        media_type="text/event-stream",
    )


@app.post("/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, body: ApprovalRequest):
    fut = PENDING_APPROVALS.get(incident_id)
    if fut and not fut.done():
        fut.set_result(body.approved)
        return {"status": "received"}
    return {"status": "no_pending_approval"}


@app.get("/health")
def health():
    return {"status": "ok"}
