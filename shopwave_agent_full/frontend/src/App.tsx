import { useEffect, useMemo, useState, type ReactNode } from 'react'

type Ticket = {
  ticket_id: string
  customer_email: string
  subject: string
  body: string
  created_at: string
  expected_action: string
}

type RunResult = {
  ticket?: Ticket
  intent?: string
  extracted_order_id?: string
  missing_fields?: string[]
  risk_flags?: string[]
  customer?: { name?: string; email?: string; tier?: string; [k: string]: unknown }
  order?: { order_id?: string; status?: string; amount?: number; product_id?: string; notes?: string; [k: string]: unknown }
  product?: { name?: string; category?: string; price?: number; [k: string]: unknown }
  kb_results?: Array<{ title?: string; content?: string; excerpt?: string; [k: string]: unknown }>
  eligibility?: { eligible?: boolean; reason?: string; amount?: number }
  decision?: { action?: string; reason?: string; reply_message?: string; priority?: string | null }
  draft_reply?: string
  escalation_summary?: string
  escalation_priority?: string
  final_status?: string
  tool_trace?: Array<Record<string, unknown>>
}

const INTENT_LABELS: Record<string, string> = {
  refund: '💰 Refund',
  return: '📦 Return',
  cancellation: '🚫 Cancellation',
  warranty: '🛡️ Warranty',
  replacement: '🔄 Replacement',
  order_status: '🔍 Order Status',
  faq: '❓ FAQ',
  clarify: '💬 Clarification',
}

const STATUS_META: Record<string, { label: string; cls: string; icon: string }> = {
  refunded:  { label: 'Refund Issued',     cls: 'status-success',  icon: '✅' },
  escalated: { label: 'Escalated',         cls: 'status-warn',     icon: '⚠️' },
  replied:   { label: 'Reply Sent',        cls: 'status-info',     icon: '💬' },
}

const TOOL_ICONS: Record<string, string> = {
  get_ticket: '🎫',
  get_customer: '👤',
  get_order: '📦',
  get_order_by_customer_email: '📦',
  get_product: '🛍️',
  search_knowledge_base: '📚',
  check_refund_eligibility: '🔎',
  issue_refund: '💰',
  escalate: '⚠️',
  send_reply: '✉️',
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className="info-value">{value}</span>
    </div>
  )
}

const API_BASE = 'http://127.0.0.1:8000'

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedTicketId, setSelectedTicketId] = useState<string>('')
  const [result, setResult] = useState<RunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetch(`${API_BASE}/tickets`)
      .then((r) => r.json())
      .then((data) => {
        setTickets(data.tickets ?? [])
        if (data.tickets?.length) setSelectedTicketId(data.tickets[0].ticket_id)
      })
      .catch(() => setError('Unable to load tickets. Start the backend first.'))
  }, [])

  const selectedTicket = useMemo(
    () => tickets.find((t) => t.ticket_id === selectedTicketId),
    [tickets, selectedTicketId],
  )

  const runAgent = async () => {
    if (!selectedTicketId) return
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket_id: selectedTicketId }),
      })
      if (!response.ok) throw new Error('Run failed')
      const data = await response.json()
      setResult(data)
    } catch (e) {
      setError('Could not run the agent. Check FastAPI and Bedrock configuration.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="hero">
        <div>
          <p className="eyebrow">LangGraph • Bedrock • Tool Orchestration</p>
          <h1>ShopWave Support Agent Console</h1>
          <p className="subtle">
            Review sample tickets, run the multi-step workflow, and inspect each tool invocation.
          </p>
        </div>
        <button className="primary" onClick={runAgent} disabled={!selectedTicketId || loading}>
          {loading ? 'Running…' : 'Run Agent'}
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="grid">
        <section className="card list-card">
          <h2>Tickets</h2>
          <div className="ticket-list">
            {tickets.map((ticket) => (
              <button
                key={ticket.ticket_id}
                className={`ticket-item ${ticket.ticket_id === selectedTicketId ? 'active' : ''}`}
                onClick={() => setSelectedTicketId(ticket.ticket_id)}
              >
                <div className="ticket-top">
                  <strong>{ticket.ticket_id}</strong>
                  <span>{new Date(ticket.created_at).toLocaleString()}</span>
                </div>
                <div className="ticket-subject">{ticket.subject}</div>
                <div className="ticket-email">{ticket.customer_email}</div>
              </button>
            ))}
          </div>
        </section>

        <section className="card details-card">
          <h2>Selected Ticket</h2>
          {selectedTicket ? (
            <>
              <div className="meta-grid">
                <div><span>Ticket</span><strong>{selectedTicket.ticket_id}</strong></div>
                <div><span>Email</span><strong>{selectedTicket.customer_email}</strong></div>
              </div>
              <h3>{selectedTicket.subject}</h3>
              <p>{selectedTicket.body}</p>
              <div className="expected">
                <span>Expected action</span>
                <strong>{selectedTicket.expected_action}</strong>
              </div>
            </>
          ) : (
            <p>No ticket selected.</p>
          )}
        </section>
      </div>

      {result ? (
        <div className="results-panel">

          {/* ── Status Banner ── */}
          {(() => {
            const fs = result.final_status ?? 'replied'
            const meta = STATUS_META[fs] ?? { label: fs, cls: 'status-info', icon: '💬' }
            return (
              <div className={`status-banner ${meta.cls}`}>
                <span className="status-icon">{meta.icon}</span>
                <div>
                  <div className="status-title">{meta.label}</div>
                  <div className="status-sub">
                    {INTENT_LABELS[result.intent ?? ''] ?? result.intent ?? 'Unknown intent'}
                    {result.extracted_order_id ? ` · ${result.extracted_order_id}` : ''}
                    {result.decision?.priority ? ` · Priority: ${result.decision.priority}` : ''}
                  </div>
                </div>
                {result.risk_flags?.length ? (
                  <div className="status-flags">
                    {result.risk_flags.map(f => <span key={f} className="flag-badge">⚑ {f.replace(/_/g, ' ')}</span>)}
                  </div>
                ) : null}
              </div>
            )
          })()}

          {/* ── Context row ── */}
          <div className="result-grid-3">

            {/* Customer */}
            <section className="card">
              <h3 className="card-section-title">👤 Customer</h3>
              {result.customer ? (
                <div className="info-table">
                  <InfoRow label="Name" value={result.customer.name ?? '—'} />
                  <InfoRow label="Email" value={result.customer.email ?? result.ticket?.customer_email ?? '—'} />
                  <InfoRow label="Tier" value={
                    <span className={`tier-badge tier-${result.customer.tier ?? 'standard'}`}>
                      {result.customer.tier ?? 'standard'}
                    </span>
                  } />
                </div>
              ) : <p className="empty-state">No customer data resolved.</p>}
            </section>

            {/* Order */}
            <section className="card">
              <h3 className="card-section-title">📦 Order</h3>
              {result.order ? (
                <div className="info-table">
                  <InfoRow label="Order ID" value={<code>{result.order.order_id ?? '—'}</code>} />
                  <InfoRow label="Status" value={
                    <span className={`status-pill order-${result.order.status}`}>
                      {result.order.status ?? '—'}
                    </span>
                  } />
                  <InfoRow label="Amount" value={result.order.amount != null ? <strong>${result.order.amount}</strong> : '—'} />
                  {result.order.notes ? <InfoRow label="Notes" value={result.order.notes} /> : null}
                </div>
              ) : <p className="empty-state">No order resolved.</p>}
            </section>

            {/* Product */}
            <section className="card">
              <h3 className="card-section-title">🛍️ Product</h3>
              {result.product ? (
                <div className="info-table">
                  <InfoRow label="Name" value={result.product.name ?? '—'} />
                  <InfoRow label="Category" value={result.product.category ?? '—'} />
                  <InfoRow label="Price" value={result.product.price != null ? `$${result.product.price}` : '—'} />
                  {(result.product as any).warranty_months ? <InfoRow label="Warranty" value={`${(result.product as any).warranty_months} months`} /> : null}
                  {(result.product as any).return_window_days ? <InfoRow label="Return window" value={`${(result.product as any).return_window_days} days`} /> : null}
                </div>
              ) : <p className="empty-state">No product data resolved.</p>}

              {result.kb_results?.length ? (
                <>
                  <h3 className="card-section-title" style={{ marginTop: 18 }}>📚 Policy Referenced</h3>
                  <div className="kb-list">
                    {result.kb_results.map((kb, i) => {
                      const text = String(kb.excerpt ?? kb.content ?? '')
                      return text ? (
                        <div key={i} className="kb-item">
                          {kb.title ? <div className="kb-title">{String(kb.title)}</div> : null}
                          <p className="kb-text">{text.slice(0, 220)}{text.length > 220 ? '…' : ''}</p>
                        </div>
                      ) : null
                    })}
                  </div>
                </>
              ) : null}
            </section>
          </div>

          {/* ── Decision + Reply ── */}
          <div className="result-grid-2">
            <section className="card">
              <h3 className="card-section-title">🤖 Agent Decision</h3>
              <div className="decision-block">
                <div className="decision-action">
                  <span className={`action-badge action-${result.decision?.action}`}>
                    {result.decision?.action?.toUpperCase() ?? 'N/A'}
                  </span>
                  <span className="decision-reason">{result.decision?.reason ?? ''}</span>
                </div>

                {result.eligibility ? (
                  <div className={`eligibility-box ${result.eligibility.eligible ? 'elig-yes' : 'elig-no'}`}>
                    <span className="elig-icon">{result.eligibility.eligible ? '✅' : '❌'}</span>
                    <div>
                      <div className="elig-title">Refund {result.eligibility.eligible ? 'Eligible' : 'Not Eligible'}</div>
                      <div className="elig-sub">
                        {result.eligibility.reason ?? ''}
                        {result.eligibility.amount != null ? ` · $${result.eligibility.amount}` : ''}
                      </div>
                    </div>
                  </div>
                ) : null}

                {result.escalation_summary ? (() => {
                  let esc: Record<string, unknown> = {}
                  try { esc = JSON.parse(result.escalation_summary!) } catch { esc = { recommended_path: result.escalation_summary } }
                  return (
                    <div className="escalation-box">
                      <div className="esc-header">⚠️ Escalated · Priority: <strong>{result.escalation_priority ?? 'high'}</strong></div>
                      {esc.recommended_path ? <p className="esc-body">{String(esc.recommended_path)}</p> : null}
                      {esc.order_id ? <p className="esc-body" style={{ margin: '4px 0 0', fontSize: 12 }}>Order: {String(esc.order_id)}</p> : null}
                    </div>
                  )
                })() : null}

                {result.missing_fields?.length ? (
                  <div className="missing-box">
                    <span className="missing-title">⚠ Missing information</span>
                    <div className="chips" style={{ marginTop: 8, marginBottom: 0 }}>
                      {result.missing_fields.map(f => <span key={f} className="chip muted">{f.replace(/_/g, ' ')}</span>)}
                    </div>
                  </div>
                ) : null}
              </div>

              <h3 className="card-section-title" style={{ marginTop: 20 }}>✉️ Customer Reply</h3>
              <div className="reply-bubble">
                {result.draft_reply ?? result.decision?.reply_message ?? 'No reply generated.'}
              </div>
            </section>

            {/* Tool Trace */}
            <section className="card">
              <h3 className="card-section-title">🔧 Tool Trace <span className="trace-count">{result.tool_trace?.length ?? 0} steps</span></h3>
              {result.tool_trace?.length ? (
                <div className="timeline">
                  {result.tool_trace.map((step, i) => {
                    const tool = String(step.tool ?? '')
                    const icon = TOOL_ICONS[tool] ?? '🔧'
                    const hasError = 'error' in step
                    return (
                      <div key={i} className={`tl-item ${hasError ? 'tl-error' : ''}`}>
                        <div className="tl-dot">{icon}</div>
                        <div className="tl-body">
                          <div className="tl-tool">{tool.replace(/_/g, ' ')}</div>
                          {step.input !== undefined ? (
                            <div className="tl-detail">
                              <span className="tl-key">in</span>
                              <code>{typeof step.input === 'object' ? JSON.stringify(step.input) : String(step.input)}</code>
                            </div>
                          ) : null}
                          {step.output !== undefined ? (
                            <div className="tl-detail">
                              <span className="tl-key">out</span>
                              <code>{typeof step.output === 'object' ? JSON.stringify(step.output) : String(step.output)}</code>
                            </div>
                          ) : null}
                          {hasError ? (
                            <div className="tl-detail tl-err-msg">
                              <span className="tl-key">error</span>
                              <code>{String(step.error)}</code>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="empty-state">No tool calls recorded.</p>
              )}
            </section>
          </div>

        </div>
      ) : (
        <div className="result-grid-2 lower-grid">
          <section className="card result-card">
            <h2>Agent Output</h2>
            <p className="empty-state">Select a ticket and click <strong>Run Agent</strong> to see the workflow results here.</p>
          </section>
          <section className="card trace-card">
            <h2>Tool Trace</h2>
            <p className="empty-state">Each tool call will appear as a step-by-step timeline after a run.</p>
          </section>
        </div>
      )}
    </div>
  )
}
