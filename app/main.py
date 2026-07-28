"""
The web server. For now it does two tiny things:

  GET /health    -> proves the server is running
  GET /test-llm  -> proves your OpenAI key actually works

Once both of these return OK, we know the foundation is solid and we can
start building the real call-testing logic on top.
"""

from dotenv import load_dotenv

# Load the .env file BEFORE we import anything that reads the API key.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import llm
from app.flow import load_flow
from app.bot_runner import BotRunner
from app.simulator import run_call
from app.personas import PERSONA_IDS
from app.evaluators import evaluate_call
from app.batch import run_batch
from app import db

app = FastAPI(title="Flow QA Harness")

# Let the React dashboard (running on port 5173) talk to us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Make sure the database and table exist before we handle any requests.
db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test-llm")
def test_llm():
    """Ask the model to say hello. If this works, the key + setup are good."""
    reply = llm.chat(
        [{"role": "user", "content": "Reply with exactly: Flow QA online."}],
        max_tokens=20,
    )
    return {"model": llm.PATIENT_MODEL, "reply": reply}


@app.get("/flow")
def get_flow():
    """
    Load the post-surgery call script and show it. Also runs a quick structure
    check so we can see any broken links or dead-end steps.
    """
    flow = load_flow()
    return {
        "flow": flow.model_dump(),
        "structure_check": {
            "broken_references": flow.broken_references(),
            "unreachable_steps": flow.unreachable_nodes(),
            "total_steps": len(flow.nodes),
        },
    }


@app.get("/test-bot")
def test_bot():
    """
    Run one canned call through the bot runner to prove it walks the script.
    A few hardcoded patient replies (healthy patient, no complications) should
    take us: greet -> recovery_intro -> fever_check -> confirm_appt -> close.
    """
    flow = load_flow()
    bot = BotRunner(flow)
    canned_patient_replies = [
        "Yes, now is a good time.",
        "It's a little sore around the cuts but nothing terrible.",
        "No fever, no chills, and the incisions look clean.",
        "Yes, Thursday at 2:30 works for me.",
    ]
    transcript = bot.run_scripted(canned_patient_replies)
    return {
        "finished": bot.finished,
        "steps_visited": bot.visited,
        "transcript": transcript,
    }


@app.get("/test-persona")
def test_persona(persona: str = "spouse"):
    """
    Run one LIVE call where the patient-AI and bot-AI actually talk.
    Defaults to the spouse persona (the privacy-leak trigger).
    Try ?persona=patient / confused_elderly / limited_english / interrupter.
    """
    if persona not in PERSONA_IDS:
        return {"error": f"unknown persona '{persona}'", "available": PERSONA_IDS}
    return run_call(persona)


@app.get("/test-eval")
def test_eval(persona: str = "spouse"):
    """
    Run one live call AND grade it. This is the whole idea in miniature:
    run the spouse -> watch the tool flag the privacy leak and point at the line.
    """
    if persona not in PERSONA_IDS:
        return {"error": f"unknown persona '{persona}'", "available": PERSONA_IDS}
    flow = load_flow()
    call = run_call(persona, flow=flow)
    report = evaluate_call(flow, call)
    return {"call": call, "report": report}


@app.post("/run")
def run(repeats: int = 2):
    """
    Run the full batch: every persona a few times, graded and saved.
    Takes a minute or so and costs a few cents. Returns the saved results.
    """
    return run_batch(repeats=repeats)


@app.get("/results")
def results():
    """Fetch the most recent saved batch (what the dashboard loads)."""
    latest = db.get_latest_run()
    if not latest:
        return {"error": "no runs yet. POST /run first."}
    return latest