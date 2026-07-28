import { useEffect, useState } from 'react'
import { getResults, runBatch } from './api'
import './dashboard.css'

// normalize text for comparing a transcript line to a check's evidence
const norm = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase()

export default function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState('Loading latest results…')
  const [openCall, setOpenCall] = useState(null)

  useEffect(() => {
    getResults()
      .then((res) => {
        if (res && res.summary) { setData(res); setNote('') }
        else setNote('No test runs yet. Click “Run tests” to start.')
      })
      .catch(() => setNote('Could not reach the backend on port 9000. Is it running?'))
  }, [])

  async function handleRun() {
    setLoading(true)
    setNote('Running calls and grading them — this takes a minute or two.')
    try {
      const res = await runBatch(2)
      if (res && res.summary) { setData(res); setNote('') }
      else setNote('The run came back empty. Check the backend terminal.')
    } catch {
      setNote('Could not reach the backend on port 9000. Is it running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-wrap">
      <header className="topbar">
        <div>
          <p className="eyebrow">Flow QA Harness</p>
          <h1 className="title">Post-Surgery Follow-Up</h1>
          {data && (
            <p className="meta">
              {data.flow?.flow_id} · run #{data.run_id} · {data.summary.total_calls} simulated calls
            </p>
          )}
        </div>
        <button className="run-btn" onClick={handleRun} disabled={loading}>
          {loading ? 'Running…' : 'Run tests'}
        </button>
      </header>

      {note && <p className="note">{note}</p>}

      {data && data.summary && (
        <>
          <Hero summary={data.summary} calls={data.calls} />
          <PersonaGrid personas={data.summary.by_persona} />
          <Coverage coverage={data.summary.coverage} />
          <CallList calls={data.calls} onOpen={setOpenCall} />
        </>
      )}

      {openCall && <TranscriptModal call={openCall} onClose={() => setOpenCall(null)} />}
    </div>
  )
}

/* ---------------------------------------------------------------- Hero */
function Hero({ summary, calls }) {
  const hasHighFail = calls.some((c) =>
    c.checks.some((k) => !k.passed && k.severity === 'high'),
  )
  const top = summary.top_failures[0]
  const rate = Math.round(summary.pass_rate * 100)

  return (
    <section className="hero">
      <div className={`stamp ${hasHighFail ? 'fail' : 'pass'}`}>
        {hasHighFail ? 'FAIL' : 'PASS'}
      </div>
      <div className="hero-body">
        <div className="hero-rate">
          {rate}<span className="unit">% call pass rate</span>
        </div>
        <div className="hero-sub">
          {summary.passed} passed · {summary.failed} failed · {summary.total_calls} calls
        </div>
        {hasHighFail ? (
          <div className="hero-callout">
            <strong>Systemic flaw:</strong> {top.check} — flagged in {top.count} of{' '}
            {summary.total_calls} calls. The script discloses patient details before it
            ever confirms who answered the phone.
          </div>
        ) : (
          <div className="hero-callout clean">
            <strong>No high-severity issues</strong> in this run.
          </div>
        )}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------- Personas */
function PersonaGrid({ personas }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">By caller type</h2>
        <p className="section-note">
          Each persona stress-tests the script differently. Red = the script fails on that caller.
        </p>
      </div>
      <div className="persona-grid">
        {personas.map((p) => {
          const tone = p.pass_rate === 1 ? 'pass' : p.pass_rate === 0 ? 'fail' : 'warn'
          return (
            <div key={p.persona_id} className={`pcard ${tone}`}>
              <p className="pcard-label">{p.label}</p>
              <div className="pbar">
                <div
                  className={`pbar-fill ${tone}`}
                  style={{ width: `${Math.max(p.pass_rate * 100, 3)}%` }}
                />
              </div>
              <p className="pcount">
                {p.passed}/{p.total} passed
                {p.failed > 0 && <span className="fail-n"> · {p.failed} failed</span>}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------- Coverage */
function Coverage({ coverage }) {
  const untested = new Set(coverage.never_visited)
  const unreachable = new Set(coverage.structurally_unreachable)
  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">Script coverage</h2>
        <p className="section-note">
          Steps the {coverage.all_steps.length}-step script has, and which ones no call ever reached.
        </p>
      </div>
      <div className="cov-strip">
        {coverage.all_steps.map((step) => {
          const isUntested = untested.has(step)
          return (
            <span key={step} className={`chip ${isUntested ? 'untested' : ''}`}>
              <span className="dot" />
              {step}
              {isUntested && (
                <span className="tag">
                  {unreachable.has(step) ? 'unreachable' : 'never tested'}
                </span>
              )}
            </span>
          )
        })}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- Calls */
function CallList({ calls, onOpen }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">All calls</h2>
        <p className="section-note">Click any call to read the transcript and see what was flagged.</p>
      </div>
      <div className="calls">
        {calls.map((c) => {
          const failed = c.checks.filter((k) => !k.passed)
          const isFail = c.verdict === 'FAIL'
          return (
            <button key={c.id} className="call-row" onClick={() => onOpen(c)}>
              <span className={`verdict-badge ${isFail ? 'fail' : 'pass'}`}>{c.verdict}</span>
              <span>
                <span className="call-persona">{c.persona_label}</span>
                <span className={`call-issue ${isFail ? '' : 'clean'}`}>
                  {isFail ? failed.map((k) => k.check).join(', ') : 'all checks passed'}
                </span>
              </span>
              <span className="call-view">view →</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

/* ------------------------------------------------------- Transcript modal */
function TranscriptModal({ call, onClose }) {
  // collect the evidence lines from failing checks so we can highlight them
  const leaks = call.checks
    .filter((k) => !k.passed && k.evidence)
    .map((k) => ({ text: norm(k.evidence), check: k.check, reason: k.reason }))

  const leakFor = (turnText) => leaks.find((l) => l.text === norm(turnText))

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3 className="modal-title">{call.persona_label}</h3>
            <p className="modal-sub">{call.id} · verdict {call.verdict}</p>
          </div>
          <button className="close-btn" onClick={onClose}>Close</button>
        </div>

        <div className="check-list">
          {call.checks.map((k, i) => (
            <div key={i} className={`check-item ${k.passed ? '' : 'fail'}`}>
              <span className={`badge ${k.passed ? 'pass' : 'fail'}`}>
                {k.passed ? 'PASS' : 'FAIL'}
              </span>
              <span>
                <span className="check-name">{k.check}</span>
                <br />
                <span className="check-reason">{k.reason}</span>
              </span>
            </div>
          ))}
        </div>

        <p className="transcript-title">Transcript</p>
        {call.transcript.map((t, i) => {
          const isBot = t.speaker === 'bot'
          const leak = isBot ? leakFor(t.text) : null
          return (
            <div key={i} className={`turn ${isBot ? 'bot' : 'caller'} ${leak ? 'leak' : ''}`}>
              <div className="speaker">{isBot ? 'Bot' : 'Caller'}</div>
              <div className="bubble">{t.text}</div>
              {leak && (
                <div className="leak-tag">
                  <strong>⚑ {leak.check}</strong>
                  <br />
                  {leak.reason}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
