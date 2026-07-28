"""
The batch runner.

Runs every persona a few times, grades each call, then rolls it all up into
the numbers the dashboard shows: pass rate overall and per persona, plus which
script steps never got exercised across the whole batch.
"""

from collections import Counter
from app.flow import load_flow
from app.personas import PERSONA_IDS, PERSONAS
from app.simulator import run_call
from app.evaluators import evaluate_call
from app import db


def run_batch(repeats: int = 2) -> dict:
    flow = load_flow()
    all_step_ids = [n.id for n in flow.nodes]

    calls = []
    visited_across_all = set()
    call_counter = 0

    for persona_id in PERSONA_IDS:
        for _ in range(repeats):
            call_counter += 1
            call = run_call(persona_id, flow=flow)
            report = evaluate_call(flow, call)
            visited_across_all.update(call.get("steps_visited", []))
            calls.append({
                "id": f"call-{call_counter}",
                "persona_id": persona_id,
                "persona_label": PERSONAS[persona_id]["label"],
                "verdict": report["verdict"],
                "checks": report["checks"],
                "steps_visited": call.get("steps_visited", []),
                "turns": call.get("turns"),
                "finished": call.get("finished"),
                "transcript": call["transcript"],
            })

    # per-persona rollup
    by_persona = []
    for persona_id in PERSONA_IDS:
        group = [c for c in calls if c["persona_id"] == persona_id]
        passed = sum(1 for c in group if c["verdict"] == "PASS")
        by_persona.append({
            "persona_id": persona_id,
            "label": PERSONAS[persona_id]["label"],
            "total": len(group),
            "passed": passed,
            "failed": len(group) - passed,
            "pass_rate": round(passed / len(group), 2) if group else 0,
        })

    # which failed checks showed up, and how often
    failure_counter = Counter()
    for c in calls:
        for chk in c["checks"]:
            if not chk["passed"]:
                failure_counter[chk["check"]] += 1
    top_failures = [{"check": k, "count": v} for k, v in failure_counter.most_common()]

    total = len(calls)
    passed_total = sum(1 for c in calls if c["verdict"] == "PASS")

    never_visited = [s for s in all_step_ids if s not in visited_across_all]

    data = {
        "flow": {
            "flow_id": flow.flow_id,
            "name": flow.name,
            "total_steps": len(all_step_ids),
        },
        "summary": {
            "total_calls": total,
            "passed": passed_total,
            "failed": total - passed_total,
            "pass_rate": round(passed_total / total, 2) if total else 0,
            "by_persona": by_persona,
            "top_failures": top_failures,
            "coverage": {
                "all_steps": all_step_ids,
                "visited_steps": sorted(visited_across_all),
                "never_visited": never_visited,
                "structurally_unreachable": flow.unreachable_nodes(),
            },
        },
        "calls": calls,
    }

    run_id = db.save_run(data)
    data["run_id"] = run_id
    return data