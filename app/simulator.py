"""
Runs one full call.

The bot says its opening line, then the bot-AI and patient-AI take turns until
the script reaches a terminal step or we hit a safety limit on turns. Returns
the whole transcript plus which steps got visited.
"""

from typing import Optional
from app.flow import load_flow, Flow
from app.bot_runner import BotRunner
from app.patient_sim import PatientSim
from app.personas import PERSONAS


def run_call(persona_id: str, flow: Optional[Flow] = None, max_turns: int = 12) -> dict:
    if persona_id not in PERSONAS:
        raise ValueError(f"Unknown persona '{persona_id}'")

    flow = flow or load_flow()
    persona = PERSONAS[persona_id]
    bot = BotRunner(flow)
    patient = PatientSim(persona)

    bot_line = bot.start()          # bot speaks first
    turns = 0
    while not bot.finished and turns < max_turns:
        patient_line = patient.reply(bot_line)
        bot_line = bot.patient_says(patient_line)
        turns += 1
        if bot_line is None:        # call ended (terminal step or dead end)
            break

    return {
        "persona_id": persona_id,
        "persona_label": persona["label"],
        "finished": bot.finished,
        "turns": turns,
        "steps_visited": bot.visited,
        "transcript": bot.transcript,
    }