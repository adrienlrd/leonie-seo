export default function ScoreCard({ score, status }) {
  if (status === 'loading') return <div className="card"><div className="label">Score SEO</div><div className="value">…</div></div>
  if (!score) return null

  const total = Math.round(score.total)
  const cls = total >= 75 ? 'score-good' : total >= 50 ? 'score-ok' : 'score-bad'
  const barColor = total >= 75 ? '#16a34a' : total >= 50 ? '#d97706' : '#dc2626'

  return (
    <div className="card">
      <div className="label">Score SEO global</div>
      <div className={`value ${cls}`}>{total}<span style={{ fontSize: '1rem', fontWeight: 400 }}>/100</span></div>
      <div className="gauge-wrap">
        <div className="gauge-bar">
          <div className="gauge-fill" style={{ width: `${total}%`, background: barColor }} />
        </div>
      </div>
    </div>
  )
}
