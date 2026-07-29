# Attune — Flow QA Harness

Attune tests AI phone-call scripts before they go live. It takes a scripted
call flow (a flowchart for what an automated care line should say), simulates
a batch of calls against it with different AI-played callers, and grades
every call for the mistakes that actually matter in healthcare: leaking
private information, drifting off the approved script, and making up facts.

The demo flow is a post-surgery follow-up call for a fictional patient,
Margaret Chen. It contains a deliberate, realistic gap: it discloses her name
and procedure before confirming who picked up the phone. Attune catches this
automatically when one of the simulated callers is her spouse instead of her.

## How it works

```
flows/*.yaml  →  BotRunner (plays the clinic)  →  PatientSim (plays the caller)  →  evaluators  →  SQLite  →  dashboard
```

1. **Flow** (`app/flow.py`) — loads a call script from YAML into a validated
   flowchart: steps ("nodes"), the line each step says, and the transitions
   to the next step based on what the caller says. It also sanity-checks the
   script for broken links and unreachable steps.

2. **BotRunner** (`app/bot_runner.py`) — plays the clinic's side of the call.
   It only ever says lines written in the script, and uses an LLM purely to
   classify which of the *script's own* allowed transitions the caller's
   reply matches. It can never improvise, so anything wrong later found in a
   call is a gap in the script, not a bug introduced by the runner.

3. **PatientSim** (`app/patient_sim.py`) — plays the caller. It's handed a
   **persona** (`app/personas.py`) — a character and situation — and replies
   in character for the whole call. Five personas ship by default:
   - the patient herself (happy path)
   - her spouse (the privacy-leak trigger — never claims to be the patient,
     but is never asked)
   - a confused elderly caller (hard of hearing, mishears questions)
   - a limited-English caller (mostly says "yes"/"okay")
   - an impatient interrupter (answers before being asked, jumps ahead)

4. **Simulator** (`app/simulator.py`) — runs one full call by alternating
   BotRunner and PatientSim turns until the script reaches a terminal step
   or a turn limit is hit.

5. **Evaluators** (`app/evaluators.py`) — grades a finished call with three
   checks:
   - **PHI leak** — did the script disclose the patient's name or procedure
     before confirming the caller's identity, to someone who turned out not
     to be the patient? Rule-based detection, LLM judgment only to decide
     who was actually on the phone.
   - **Off-script** — did the bot ever say something that isn't one of the
     script's approved lines? Pure string matching against the script.
   - **Hallucination** — did the bot state a fact that contradicts or isn't
     grounded in the patient record? LLM judge, explicitly instructed not to
     flag paraphrasing or ordinary questions.

6. **Batch runner** (`app/batch.py`) — runs every persona a few times each,
   grades every call, and rolls the results up into an overall pass rate,
   a per-persona breakdown, the most common failures, and which script steps
   were never exercised by any call. The batch is saved to SQLite
   (`app/db.py`) and served to the dashboard.

## Project layout

```
app/               FastAPI backend
  main.py          Routes (see below)
  flow.py          YAML flow loader + structural validation
  bot_runner.py    Deterministic, script-bound clinic AI
  patient_sim.py   Character-driven caller AI
  personas.py      The five caller personas
  simulator.py     Runs one full call
  evaluators.py    PHI leak / off-script / hallucination checks
  batch.py         Runs + grades a full batch, builds the summary
  db.py            SQLite storage for saved runs
  llm.py           Single place all OpenAI calls go through
flows/
  post_surgery_followup.yaml   The demo call script
frontend/          React + Vite dashboard
  src/App.jsx      Pass-rate hero, per-persona grid, coverage strip,
                   call list, and a transcript viewer that highlights
                   the exact flagged line
requirements.txt   Python dependencies
```

## Running it

**Backend**

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
PATIENT_MODEL=gpt-4o-mini    # optional, this is the default
JUDGE_MODEL=gpt-4o           # optional, this is the default
```

```bash
uvicorn app.main:app --reload --port 9000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Then open the Vite dev server (defaults to `http://localhost:5173`) and
click **Run tests** to kick off a batch against the backend on port 9000.

## API

| Route | Method | What it does |
|---|---|---|
| `/health` | GET | Confirms the server is up |
| `/test-llm` | GET | Confirms the OpenAI key works |
| `/flow` | GET | Loads the demo flow + structural validation |
| `/test-bot` | GET | Runs one scripted call through BotRunner only |
| `/test-persona?persona=` | GET | Runs one live call for a given persona |
| `/test-eval?persona=` | GET | Runs one live call and grades it |
| `/run?repeats=` | POST | Runs the full batch (every persona × `repeats`), grades and saves it |
| `/results` | GET | Returns the most recently saved batch |

## Notes

- Model choice is split on purpose: a cheaper model plays the patient and
  classifies intents, while a stronger model is reserved for grading
  (`JUDGE_MODEL`), since that's where judgment actually matters.
- `flowqa.db`, `venv/`, `.env`, and `frontend/node_modules` are all
  git-ignored — the API key never leaves your machine.
