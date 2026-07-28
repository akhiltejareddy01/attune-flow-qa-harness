"""
The bot runner = the AI playing the clinic's side of the call.

It walks the script one step at a time. At each step it:
  1. says the step's written line (and ONLY that line -- never improvises),
  2. hears the patient's reply,
  3. asks the LLM a narrow question: "which of this step's allowed answers
     does that reply match?",
  4. follows the script's arrow to the next step (or the fallback if nothing
     matched),
  5. stops when it reaches a step marked "terminal".

Because it can only ever say scripted lines and follow scripted arrows, any
problem the harness later finds is a hole in the SCRIPT, not a bug we added.
That is exactly Attune's "deterministic, never off-script" promise.
"""

from typing import List, Dict, Optional
from app import llm
from app.flow import Flow, Node


class BotRunner:
    def __init__(self, flow: Flow, model: Optional[str] = None):
        self.flow = flow
        self.current_id = flow.start
        # classification is cheap, so use the cheaper model by default
        self.model = model or llm.PATIENT_MODEL
        self.transcript: List[Dict] = []   # the full back-and-forth
        self.visited: List[str] = []       # which steps this call touched
        self.finished = False

    def current_node(self) -> Node:
        return self.flow.node(self.current_id)

    def _record_bot(self, node: Node):
        self.transcript.append(
            {"speaker": "bot", "node": node.id, "text": node.say.strip()}
        )
        if node.id not in self.visited:
            self.visited.append(node.id)
        if node.kind == "terminal":
            self.finished = True

    def start(self) -> str:
        """Bot says its opening line and returns it."""
        node = self.current_node()
        self._record_bot(node)
        return node.say.strip()

    def _classify(self, patient_text: str) -> str:
        """Ask the LLM which allowed answer the patient's reply matches."""
        node = self.current_node()
        intents = list(node.transitions.keys())
        if not intents:
            return "none"

        options = "\n".join(f"- {name}" for name in intents)
        system = (
            "You are a strict intent classifier for a scripted healthcare phone "
            "call. You get what the agent just said, the caller's reply, and a "
            "list of allowed labels. Pick the ONE label that best matches the "
            "reply. If none clearly match, answer exactly: none. Reply with only "
            "the label text and nothing else."
        )
        user = (
            f'Agent said: "{node.say.strip()}"\n\n'
            f'Caller replied: "{patient_text}"\n\n'
            f"Allowed labels:\n{options}\n\n"
            "Which single label matches? Reply with just the label, or 'none'."
        )
        raw = llm.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            model=self.model,
            temperature=0,
            max_tokens=10,
        )
        label = raw.strip().strip('".').lower()
        for name in intents:
            if name.lower() == label:
                return name
        return "none"

    def patient_says(self, patient_text: str) -> Optional[str]:
        """
        Feed in the patient's reply. Returns the bot's next line, or None if the
        call has ended.
        """
        if self.finished:
            return None

        node = self.current_node()
        turn = {"speaker": "patient", "text": patient_text, "from_node": node.id}

        matched = self._classify(patient_text)
        if matched != "none" and matched in node.transitions:
            next_id = node.transitions[matched]
            turn["matched_intent"] = matched
        else:
            next_id = node.fallback
            turn["matched_intent"] = "none -> fallback" if next_id else "none (no fallback)"

        turn["to_node"] = next_id
        self.transcript.append(turn)

        if not next_id:
            # No arrow and no fallback: the call just stops here.
            self.finished = True
            return None

        self.current_id = next_id
        new_node = self.current_node()
        self._record_bot(new_node)
        return new_node.say.strip()

    def run_scripted(self, patient_lines: List[str]) -> List[Dict]:
        """
        Convenience for testing: play a fixed list of patient replies straight
        through and return the full transcript.
        """
        self.start()
        for line in patient_lines:
            if self.finished:
                break
            self.patient_says(line)
        return self.transcript