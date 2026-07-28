"""
The patient's side of the call.

Given a persona, this plays the caller: it hears what the bot says and replies
naturally, staying in character. From this AI's point of view, the bot's lines
are the incoming messages and its own replies are the responses.
"""

from typing import Optional
from app import llm

# Rules that apply to every persona, on top of their character instructions.
_PHONE_GUIDANCE = (
    "\n\nYou are on a phone call and the caller is an automated care line. "
    "Reply the way a real person would speak on the phone: short, natural, "
    "usually one or two sentences. Stay fully in character at all times. Never "
    "say that you are an AI, and never mention that this is a test or "
    "simulation. If the call reaches a natural end, it is fine to say goodbye."
)


class PatientSim:
    def __init__(self, persona: dict, model: Optional[str] = None):
        self.persona = persona
        self.model = model or llm.PATIENT_MODEL
        self.messages = [
            {"role": "system", "content": persona["instructions"] + _PHONE_GUIDANCE}
        ]

    def reply(self, bot_line: str) -> str:
        """Hear the bot's line, respond in character."""
        self.messages.append({"role": "user", "content": bot_line})
        out = llm.chat(
            self.messages,
            model=self.model,
            temperature=0.8,   # a little variety so calls aren't identical
            max_tokens=80,
        )
        self.messages.append({"role": "assistant", "content": out})
        return out