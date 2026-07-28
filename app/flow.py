"""
Reads a call script (a .yaml file) off disk, checks it makes sense, and gives
the rest of the app a clean object to work with.

Think of a "flow" as a flowchart for a phone call:
  - each "node" is one step (what the AI says + where it can go next)
  - "transitions" map what the caller does to the next step
  - "start" is the first step

This file does NOT call any AI. It just loads and sanity-checks the script.
"""

import os
import yaml
from typing import Dict, List, Optional
from pydantic import BaseModel

# The flows folder sits next to the app folder: backend/flows/
FLOWS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flows")


class Node(BaseModel):
    id: str
    say: str
    kind: str = "step"                      # "step" or "terminal" (call ends)
    transitions: Dict[str, str] = {}        # caller-intent -> next node id
    fallback: Optional[str] = None          # where to go if nothing matched


class PatientRecord(BaseModel):
    patient_name: str
    procedure: str
    surgery_date: str
    surgeon: str
    followup: str


class Flow(BaseModel):
    flow_id: str
    name: str
    description: str = ""
    goal: str = ""
    start: str
    patient_record: PatientRecord
    nodes: List[Node]

    # --- convenience helpers -------------------------------------------------

    def node(self, node_id: str) -> Optional[Node]:
        """Get one step by its id."""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def all_next_ids(self, node: Node) -> List[str]:
        """Every step this step can lead to (transitions + fallback)."""
        ids = list(node.transitions.values())
        if node.fallback:
            ids.append(node.fallback)
        return ids

    # --- structure checks ----------------------------------------------------

    def broken_references(self) -> List[str]:
        """Steps that point to a next-step id that doesn't exist."""
        known = {n.id for n in self.nodes}
        problems = []
        if self.start not in known:
            problems.append(f"start step '{self.start}' does not exist")
        for n in self.nodes:
            for target in self.all_next_ids(n):
                if target not in known:
                    problems.append(f"'{n.id}' points to missing step '{target}'")
        return problems

    def unreachable_nodes(self) -> List[str]:
        """
        Steps you can never actually get to from the start. Walks the flow like
        a caller would and notes which steps were never visited.
        """
        known = {n.id for n in self.nodes}
        seen = set()
        stack = [self.start] if self.start in known else []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            node = self.node(current)
            if node:
                for target in self.all_next_ids(node):
                    if target in known and target not in seen:
                        stack.append(target)
        return sorted(known - seen)


def load_flow(filename: str = "post_surgery_followup.yaml") -> Flow:
    """Load and validate a flow file from the flows folder."""
    path = os.path.join(FLOWS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No flow file found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Flow(**data)