import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MetaApplyPanel({ shop }) {
  const [suggestions, setSuggestions] = useState([])
  const [edits, setEdits] = useState({})
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [applied, setApplied] = useState(false)

  // Load meta suggestions from the raw JSON produced by generate_suggestions
  useEffect(() => {
    if (!shop) return
    fetch('/data/raw/meta_suggestions.json')
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setSuggestions(Array.isArray(data) ? data.slice(0, 10) : [])
        setEdits({})
        setResults([])
        setApplied(false)
      })
      .catch(() => setSuggestions([]))
  }, [shop])

  const handleChange = (id, field, value) => {
    setEdits(prev => ({ ...prev, [id]: { ...(prev[id] || {}), [field]: value } }))
  }

  const buildUpdates = () =>
    suggestions.map(s => ({
      product_id: s.product_id,
      title: edits[s.product_id]?.title ?? s.suggested_title ?? null,
      description: edits[s.product_id]?.description ?? s.suggested_description ?? null,
    }))

  const run = async (dryRun) => {
    setLoading(true)
    setResults([])
    try {
      const res = await api.applyMeta(shop, buildUpdates(), dryRun)
      setResults(res)
      if (!dryRun) setApplied(true)
    } catch (e) {
      setResults([{ status: 'error', detail: e.message }])
    } finally {
      setLoading(false)
    }
  }

  if (!shop) return <div className="apply-wrap"><div className="empty">Sélectionnez une boutique</div></div>

  return (
    <div className="apply-wrap">
      <h2>Appliquer des corrections meta</h2>
      <p className="hint">
        Les suggestions viennent de <code>data/raw/meta_suggestions.json</code>.
        Prévisualisez d'abord, puis confirmez pour envoyer à Shopify.
      </p>

      {suggestions.length === 0 && (
        <div className="empty">Aucune suggestion disponible. Lancez d'abord <code>leonie-seo report generate-suggestions</code>.</div>
      )}

      {suggestions.length > 0 && (
        <div className="suggestion-list">
          {suggestions.map(s => (
            <div key={s.product_id} className="suggestion-item">
              <div className="prod-title">{s.product_title}</div>
              <label>Meta title</label>
              <input
                value={edits[s.product_id]?.title ?? s.suggested_title ?? ''}
                onChange={e => handleChange(s.product_id, 'title', e.target.value)}
                placeholder="Meta title…"
              />
              <label>Meta description</label>
              <input
                value={edits[s.product_id]?.description ?? s.suggested_description ?? ''}
                onChange={e => handleChange(s.product_id, 'description', e.target.value)}
                placeholder="Meta description…"
              />
            </div>
          ))}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="btn-row">
          <button className="btn btn-preview" onClick={() => run(true)} disabled={loading}>
            {loading ? 'Chargement…' : '👁 Prévisualiser'}
          </button>
          <button className="btn btn-apply" onClick={() => run(false)} disabled={loading || applied}>
            {applied ? '✅ Appliqué' : '🚀 Appliquer sur Shopify'}
          </button>
        </div>
      )}

      {results.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          {results.map((r, i) => (
            <div key={i} className={`result-${r.status}`} style={{ fontSize: '0.82rem', marginBottom: '0.3rem' }}>
              {r.status === 'applied' && `✅ ${r.product_id} — appliqué`}
              {r.status === 'preview' && `👁 ${r.detail}`}
              {r.status === 'error' && `❌ ${r.detail}`}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
