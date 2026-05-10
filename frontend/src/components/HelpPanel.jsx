import { useEffect, useState } from 'react'
import { api } from '../api'

export default function HelpPanel({ lang = 'fr' }) {
  const [faq, setFaq] = useState(null)
  const [open, setOpen] = useState(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getFaq(lang)
      .then(setFaq)
      .catch(e => setError(e.message))
  }, [lang])

  if (error) return <div className="error-msg">{error}</div>
  if (!faq) return <div className="empty">Chargement de l'aide…</div>

  const filtered = search.trim()
    ? faq.items.filter(
        item =>
          item.question.toLowerCase().includes(search.toLowerCase()) ||
          item.answer.toLowerCase().includes(search.toLowerCase())
      )
    : faq.items

  const byCategory = faq.categories.reduce((acc, cat) => {
    acc[cat.id] = { label: cat.label, items: filtered.filter(i => i.category === cat.id) }
    return acc
  }, {})

  return (
    <div className="help-panel">
      <h2 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 600 }}>
        {lang === 'fr' ? 'Centre d'aide' : 'Help center'}
      </h2>

      <input
        type="search"
        className="help-search"
        placeholder={lang === 'fr' ? 'Rechercher…' : 'Search…'}
        value={search}
        onChange={e => setSearch(e.target.value)}
      />

      {faq.categories.map(cat => {
        const { label, items } = byCategory[cat.id]
        if (items.length === 0) return null
        return (
          <div key={cat.id} className="help-category">
            <h3>{label}</h3>
            {items.map(item => (
              <div key={item.id} className="help-item">
                <button
                  className={`help-question ${open === item.id ? 'open' : ''}`}
                  onClick={() => setOpen(open === item.id ? null : item.id)}
                >
                  {item.question}
                  <span className="help-chevron">{open === item.id ? '▲' : '▼'}</span>
                </button>
                {open === item.id && (
                  <div className="help-answer">{item.answer}</div>
                )}
              </div>
            ))}
          </div>
        )
      })}

      {filtered.length === 0 && (
        <div className="empty">
          {lang === 'fr' ? 'Aucun résultat pour cette recherche.' : 'No results for this search.'}
        </div>
      )}

      <div className="help-footer">
        <a
          href="docs/guide-utilisateur.fr.md"
          target="_blank"
          rel="noreferrer"
        >
          {lang === 'fr' ? '📄 Guide complet (FR)' : '📄 Full guide (FR)'}
        </a>
        {' · '}
        <a
          href="docs/user-guide.en.md"
          target="_blank"
          rel="noreferrer"
        >
          📄 User guide (EN)
        </a>
      </div>
    </div>
  )
}
