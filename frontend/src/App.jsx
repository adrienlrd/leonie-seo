import { useEffect, useState } from 'react'
import IssuesList from './components/IssuesList'
import MetaApplyPanel from './components/MetaApplyPanel'
import ScoreCard from './components/ScoreCard'
import { api } from './api'
import './styles.css'

const VIEWS = ['dashboard', 'issues', 'appliquer']
const VIEW_LABELS = { dashboard: 'Dashboard', issues: 'Issues', appliquer: 'Appliquer' }

// Resolve the active shop from (priority): URL ?shop=… → localStorage → empty
function resolveInitialShop() {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = params.get('shop')
  if (fromUrl) {
    localStorage.setItem('leonie:shop', fromUrl)
    return fromUrl
  }
  return localStorage.getItem('leonie:shop') || ''
}

export default function App() {
  const [view, setView] = useState('dashboard')
  const [shop, setShop] = useState(resolveInitialShop)
  const [shops, setShops] = useState([])

  const [status, setStatus] = useState(null)
  const [score, setScore] = useState(null)
  const [scoreLoading, setScoreLoading] = useState(false)
  const [issues, setIssues] = useState([])
  const [issuesLoading, setIssuesLoading] = useState(false)
  const [issuesError, setIssuesError] = useState(null)
  const [error, setError] = useState(null)

  // Load installed shops from OAuth table; fall back to current shop only
  useEffect(() => {
    api.listShops()
      .then(data => {
        const installed = data.map(s => s.shop)
        const all = shop && !installed.includes(shop) ? [shop, ...installed] : installed
        setShops(all)
        if (!shop && installed.length > 0) {
          setShop(installed[0])
          localStorage.setItem('leonie:shop', installed[0])
        }
      })
      .catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist shop selection
  useEffect(() => {
    if (shop) localStorage.setItem('leonie:shop', shop)
  }, [shop])

  // Load shop status + score when shop changes
  useEffect(() => {
    if (!shop) return
    setStatus(null)
    setScore(null)
    setError(null)

    api.shopStatus(shop)
      .then(setStatus)
      .catch(e => setError(e.message))

    setScoreLoading(true)
    api.getScore(shop)
      .then(s => { setScore(s); setScoreLoading(false) })
      .catch(() => setScoreLoading(false))
  }, [shop])

  // Load issues when switching to issues view
  useEffect(() => {
    if (view !== 'issues' || !shop) return
    setIssuesLoading(true)
    setIssuesError(null)
    api.getIssues(shop)
      .then(data => { setIssues(data); setIssuesLoading(false) })
      .catch(e => { setIssuesError(e.message); setIssuesLoading(false) })
  }, [view, shop])

  const criticalCount = issues.filter(i => i.severity === 'critical').length
  const highCount = issues.filter(i => i.severity === 'high').length

  return (
    <div className="app">
      <header>
        <h1>Léonie SEO</h1>
        <span className="tag">BETA</span>
        {status?.plan && (
          <span className={`tag tag-plan tag-plan-${status.plan}`}>{status.plan.toUpperCase()}</span>
        )}
        <nav>
          {VIEWS.map(v => (
            <button key={v} className={view === v ? 'active' : ''} onClick={() => setView(v)}>
              {VIEW_LABELS[v]}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {/* Shop selector */}
        <div className="shop-selector">
          <label>Boutique</label>
          {shops.length > 0 ? (
            <select value={shop} onChange={e => setShop(e.target.value)}>
              {shops.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          ) : (
            <input
              type="text"
              placeholder="xxx.myshopify.com"
              value={shop}
              onChange={e => setShop(e.target.value)}
              style={{ padding: '0.5rem 0.75rem', border: '1px solid #ddd', borderRadius: 8, fontSize: '0.875rem' }}
            />
          )}
          {status && <span style={{ fontSize: '0.78rem', color: '#888' }}>
            {status.snapshot_available
              ? `${status.product_count} produits · ${status.collection_count} collections`
              : '⚠ Aucun crawl — lancez leonie-seo audit crawl'}
          </span>}
        </div>

        {!shop && (
          <div className="empty">
            Aucune boutique configurée. Ajoute <code>?shop=xxx.myshopify.com</code> à l'URL,
            ou installe l'app via OAuth.
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        {/* ── Dashboard ── */}
        {view === 'dashboard' && (
          <>
            <div className="cards">
              <ScoreCard score={score} status={scoreLoading ? 'loading' : 'ok'} />
              <div className="card">
                <div className="label">Produits</div>
                <div className="value">{status?.product_count ?? '—'}</div>
              </div>
              <div className="card">
                <div className="label">Issues critiques</div>
                <div className="value score-bad">{issues.length ? criticalCount : '—'}</div>
                <div className="sub">Chargées depuis l'onglet Issues</div>
              </div>
              <div className="card">
                <div className="label">Issues high</div>
                <div className="value score-ok">{issues.length ? highCount : '—'}</div>
                <div className="sub">Chargées depuis l'onglet Issues</div>
              </div>
            </div>
            {score && (
              <div className="table-wrap" style={{ padding: '1.25rem 1.5rem' }}>
                <h2 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>Détail du score</h2>
                <table>
                  <thead><tr><th>Composant</th><th>Score</th><th>Jauge</th></tr></thead>
                  <tbody>
                    {Object.entries(score.components).map(([k, v]) => {
                      const pct = Math.round(v * 100)
                      const color = pct >= 75 ? '#16a34a' : pct >= 50 ? '#d97706' : '#dc2626'
                      return (
                        <tr key={k}>
                          <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{k}</td>
                          <td className={pct >= 75 ? 'score-good' : pct >= 50 ? 'score-ok' : 'score-bad'} style={{ fontWeight: 600 }}>{pct}%</td>
                          <td style={{ width: '40%' }}>
                            <div className="gauge-bar">
                              <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ── Issues ── */}
        {view === 'issues' && (
          <IssuesList issues={issues} loading={issuesLoading} error={issuesError} />
        )}

        {/* ── Appliquer ── */}
        {view === 'appliquer' && <MetaApplyPanel shop={shop} />}
      </main>
    </div>
  )
}
