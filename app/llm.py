"""
Single place we talk to the LLM.

Everything else in the app calls chat() from here, so if we ever want to
swap models (cheaper one for the fake patient, smarter one for grading),
we only change it in this one file.

The API key is read from the environment ONLY. Never hard-code it.
"""

import os
from openai import OpenAI

# Read the key from the environment. If it's missing we fail loudly and clearly.
_API_KEY = os.getenv("OPENAI_API_KEY")
if not _API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Copy .env.example to .env, paste your key, "
        "and make sure your virtual environment loaded it."
    )

client = OpenAI(api_key=_API_KEY)

# Two "roles" of model so we can spend money where it matters.
# The patient can be a cheaper model; grading should be a stronger one.
PATIENT_MODEL = os.getenv("PATIENT_MODEL", "gpt-4o-mini")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o")


def chat(messages, model=PATIENT_MODEL, temperature=0.7, max_tokens=400):
    """
    Send a list of messages to the model and get back plain text.

    messages looks like: [{"role": "system", "content": "..."},
                          {"role": "user", "content": "..."}]
    """
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()