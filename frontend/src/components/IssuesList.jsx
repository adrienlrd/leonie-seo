import { useState } from 'react'

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low', 'info']

export default function IssuesList({ issues, loading, error }) {
  const [filter, setFilter] = useState('all')

  const displayed = filter === 'all' ? issues : issues.filter(i => i.severity === filter)

  return (
    <div className="table-wrap">
      <div className="table-header">
        <h2>Issues SEO ({displayed.length})</h2>
        <div className="filter-bar">
          {SEVERITIES.map(s => (
            <button key={s} className={filter === s ? 'active' : ''} onClick={() => setFilter(s)}>
              {s === 'all' ? 'Toutes' : s}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="loading">Chargement…</div>}
      {error && <div className="error-msg">{error}</div>}

      {!loading && !error && (
        displayed.length === 0
          ? <div className="empty">Aucune issue{filter !== 'all' ? ` de sévérité « ${filter} »` : ''} 🎉</div>
          : (
            <table>
              <thead>
                <tr>
                  <th>Sévérité</th>
                  <th>Type</th>
                  <th>Ressource</th>
                  <th>Détail</th>
                </tr>
              </thead>
              <tbody>
                {displayed.map((issue, i) => (
                  <tr key={i}>
                    <td><span className={`badge badge-${issue.severity}`}>{issue.severity}</span></td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{issue.issue_type}</td>
                    <td>{issue.resource_title}</td>
                    <td style={{ color: '#555' }}>{issue.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
      )}
    </div>
  )
}
