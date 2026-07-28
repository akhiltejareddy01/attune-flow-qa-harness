// All calls go to the FastAPI backend running on port 9000.
const BASE = 'http://127.0.0.1:9000'

export async function getResults() {
  const res = await fetch(`${BASE}/results`)
  return res.json()
}

export async function runBatch(repeats = 2) {
  const res = await fetch(`${BASE}/run?repeats=${repeats}`, { method: 'POST' })
  return res.json()
}
