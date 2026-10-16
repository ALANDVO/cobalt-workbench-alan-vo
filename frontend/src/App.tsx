import { useState, useEffect } from 'react'
import { getHealth, getACPStatus, type HealthResponse, type ACPStatusResponse, type SessionSummary } from './api/client'
import './App.css'

function StatusBadge({ status, label }: { status: string; label: string }) {
  const colors: Record<string, string> = {
    healthy: 'var(--color-success)',
    ready: 'var(--color-success)',
    unhealthy: 'var(--color-error)',
    degraded: 'var(--color-warning)',
  }
  const bgColor = colors[status] || 'var(--color-text-muted)'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 10px',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: 600,
        backgroundColor: `${bgColor}20`,
        color: bgColor,
        border: `1px solid ${bgColor}40`,
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: bgColor,
        }}
      />
      {label}: {status}
    </span>
  )
}

function StatCard({ title, value, subtitle }: { title: string; value: string | number; subtitle?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-title">{title}</div>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="stat-subtitle">{subtitle}</div>}
    </div>
  )
}

function SessionRow({ session }: { session: SessionSummary }) {
  const savingsPct = session.total_original_tokens > 0
    ? Math.round((1 - session.overall_compression_ratio) * 100)
    : 0
  return (
    <tr>
      <td><code>{session.session_id}</code></td>
      <td>{session.agent_namespace}</td>
      <td>{session.conversation_id}</td>
      <td>{session.total_messages.toLocaleString()}</td>
      <td>{session.total_original_tokens.toLocaleString()}</td>
      <td>{session.total_folded_tokens.toLocaleString()}</td>
      <td><span className="compression-ratio">{savingsPct}% saved</span></td>
      <td>{session.fold_count}</td>
      <td>{session.last_fold_at ? new Date(session.last_fold_at).toLocaleString() : '—'}</td>
    </tr>
  )
}

function FoldRow({ fold }: { fold: { fold_id: string; original_tokens: number; folded_tokens: number; compression_ratio: number; anchor_count: number; covered_message_count: number; created_at: string } }) {
  const ratioPct = Math.round(fold.compression_ratio * 100)
  return (
    <tr>
      <td><code>{fold.fold_id}</code></td>
      <td>{fold.original_tokens.toLocaleString()}</td>
      <td>{fold.folded_tokens.toLocaleString()}</td>
      <td><span className="compression-ratio">{ratioPct}%</span></td>
      <td>{fold.anchor_count}</td>
      <td>{fold.covered_message_count}</td>
      <td>{new Date(fold.created_at).toLocaleString()}</td>
    </tr>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [acpStatus, setAcpStatus] = useState<ACPStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchData() {
    try {
      setError(null)
      const [h, a] = await Promise.all([getHealth(), getACPStatus()])
      setHealth(h)
      setAcpStatus(a)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading && !health) {
    return (
      <div className="app loading">
        <div className="spinner" />
        <p>Loading Cobalt Workbench...</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1 className="title">
            <span className="logo">◆</span>
            Cobalt Workbench
          </h1>
          <p className="subtitle">AI/ML Context Compression — 5x token savings, month-long sessions</p>
          <div className="status-badges">
            <StatusBadge status={health?.status || 'unknown'} label="Backend" />
            <StatusBadge status={acpStatus?.enabled ? 'healthy' : 'degraded'} label="ACP" />
          </div>
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={fetchData} className="retry-btn">Retry</button>
        </div>
      )}

      <main className="main">
        <section className="panel stats-panel">
          <h2>Overview</h2>
          <div className="stats-grid">
            <StatCard
              title="Active Sessions"
              value={acpStatus?.active_sessions || 0}
              subtitle="Compressed conversations"
            />
            <StatCard
              title="Total Folds"
              value={acpStatus?.total_folds || 0}
              subtitle="Compression operations"
            />
            <StatCard
              title="Tokens Saved"
              value={acpStatus?.total_tokens_saved?.toLocaleString() || 0}
              subtitle="vs. uncompressed history"
            />
            <StatCard
              title="Compression Target"
              value={`${Math.round((acpStatus?.compression_target_ratio || 0.2) * 100)}%`}
              subtitle={`${(1 / (acpStatus?.compression_target_ratio || 0.2)).toFixed(1)}x reduction`}
            />
            <StatCard
              title="Context Window"
              value={`${(acpStatus?.default_window_tokens || 100000).toLocaleString()}`}
              subtitle="tokens"
            />
            <StatCard
              title="Fold Threshold"
              value={`${(acpStatus?.fold_threshold_tokens || 80000).toLocaleString()}`}
              subtitle="tokens"
            />
          </div>
        </section>

        <section className="panel sessions-panel">
          <h2>Active Sessions</h2>
          {acpStatus?.sessions.length ? (
            <div className="table-wrapper scrollbar-thin">
              <table>
                <thead>
                  <tr>
                    <th>Session ID</th>
                    <th>Agent</th>
                    <th>Conversation</th>
                    <th>Messages</th>
                    <th>Original Tokens</th>
                    <th>Folded Tokens</th>
                    <th>Compression</th>
                    <th>Folds</th>
                    <th>Last Fold</th>
                  </tr>
                </thead>
                <tbody>
                  {acpStatus.sessions.map((session) => (
                    <SessionRow key={session.session_id} session={session} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-state">No active sessions. Start a conversation through your AI client.</p>
          )}
        </section>

        <section className="panel folds-panel">
          <h2>Recent Folds</h2>
          {acpStatus?.recent_folds.length ? (
            <div className="table-wrapper scrollbar-thin">
              <table>
                <thead>
                  <tr>
                    <th>Fold ID</th>
                    <th>Original Tokens</th>
                    <th>Folded Tokens</th>
                    <th>Ratio</th>
                    <th>Anchors</th>
                    <th>Covered Msgs</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {acpStatus.recent_folds.map((fold) => (
                    <FoldRow key={fold.fold_id} fold={fold} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-state">No folds yet. Compression runs automatically when threshold is reached.</p>
          )}
        </section>

        <section className="panel config-panel">
          <h2>Configuration</h2>
          <dl className="config-list">
            <div><dt>ACP Enabled</dt><dd>{acpStatus?.enabled ? 'Yes' : 'No'}</dd></div>
            <div><dt>Default Window</dt><dd>{acpStatus?.default_window_tokens?.toLocaleString()} tokens</dd></div>
            <div><dt>Target Ratio</dt><dd>{Math.round((acpStatus?.compression_target_ratio || 0) * 100)}%</dd></div>
            <div><dt>Fold Threshold</dt><dd>{acpStatus?.fold_threshold_tokens?.toLocaleString()} tokens</dd></div>
            <div><dt>Service</dt><dd>{health?.service} v{health?.version}</dd></div>
            <div><dt>Environment</dt><dd>{health?.environment}</dd></div>
          </dl>
        </section>
      </main>

      <footer className="footer">
        <p>Cobalt Workbench \u2014 Alan Vo (alanvo@gmail.com) | AI & Machine Learning</p>
      </footer>
    </div>
  )
}