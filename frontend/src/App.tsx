import { useState, useEffect } from 'react'
import { getHealth, getACPStatus, searchContext, type HealthResponse, type ACPStatusResponse, type SessionSummary, type SearchContextResult, type SearchContextResponse } from './api/client'
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
function SearchResultRow({ result }: { result: SearchContextResult }) {
  const scorePct = Math.round(result.score * 100)
  return (
    <tr>
      <td><code>{result.anchor_id}</code></td>
      <td className="search-summary-cell">{result.summary}</td>
      <td><span className="compression-ratio">{scorePct}%</span></td>
      <td>{result.original_tokens.toLocaleString()}</td>
      <td>{result.covered_message_ids.length}</td>
      <td>{result.start_idx}–{result.end_idx}</td>
    </tr>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [acpStatus, setAcpStatus] = useState<ACPStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchContextResponse | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

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

  async function handleSearch() {
    if (!searchQuery.trim() || !acpStatus) return

    setSearchLoading(true)
    setSearchError(null)
    setSearchResults(null)

    try {
      // Collect all fold anchors from recent folds and sessions
      const allAnchors: Record<string, unknown>[] = []

      // Add anchors from recent folds (mock data structure)
      for (const fold of acpStatus.recent_folds) {
        // In a real implementation, fold_anchors would come from the fold data
        // For now, create a mock anchor from fold data
        allAnchors.push({
          id: fold.fold_id,
          summary: `Fold with ${fold.anchor_count} anchors, ${fold.covered_message_count} messages`,
          covered_message_ids: [],
          start_idx: 0,
          end_idx: fold.covered_message_count - 1,
          original_tokens: fold.original_tokens,
          folded_tokens: fold.folded_tokens,
        })
      }

      const response = await searchContext({
        query: searchQuery,
        fold_anchors: allAnchors,
        max_results: 10,
        min_score: 0.1,
      })
      setSearchResults(response)
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setSearchLoading(false)
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

        </section>

        <section className="panel search-panel">
          <h2>Search Context</h2>
          <div className="search-form">
            <input
              type="text"
              placeholder="Search compressed conversation folds..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="search-input"
            />
            <button onClick={handleSearch} disabled={searchLoading || !searchQuery.trim()} className="search-btn">
              {searchLoading ? 'Searching...' : 'Search'}
            </button>
          </div>
          {searchError && (
            <div className="search-error" role="alert">
              <span>⚠</span>
              <span>{searchError}</span>
            </div>
          )}
          {searchResults !== null && (
            <div className="search-results">
              {searchResults.results_count === 0 ? (
                <p className="empty-state">No matching folds found for "{searchQuery}".</p>
              ) : (
                <>
                  <p className="search-summary">
                    Found {searchResults.results_count} of {searchResults.total_anchors_searched} folds matching "{searchQuery}"
                  </p>
                  <div className="table-wrapper scrollbar-thin">
                    <table>
                      <thead>
                        <tr>
                          <th>Anchor ID</th>
                          <th>Summary</th>
                          <th>Score</th>
                          <th>Original Tokens</th>
                          <th>Covered Msgs</th>
                          <th>Index Range</th>
                        </tr>
                      </thead>
                      <tbody>
                        {searchResults.results.map((result: SearchContextResult) => (
                          <SearchResultRow key={result.anchor_id} result={result} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
        </section>
      </main>

      <footer className="footer">
        <p>Cobalt Workbench \u2014 Alan Vo (alanvo@gmail.com) | AI & Machine Learning</p>
      </footer>
    </div>
  )
}