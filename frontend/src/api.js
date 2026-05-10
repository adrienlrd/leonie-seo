import { getSessionToken } from './auth'

const BASE = '/api'

async function _headers(extra = {}) {
  const token = await getSessionToken()
  return token
    ? { ...extra, Authorization: `Bearer ${token}` }
    : extra
}

async function _get(path) {
  const headers = await _headers()
  const res = await fetch(BASE + path, { headers })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

async function _post(path, body) {
  const headers = await _headers({ 'Content-Type': 'application/json' })
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  listShops: () => _get('/shops'),
  shopStatus: (shop) => _get(`/shops/${shop}/status`),
  getIssues: (shop, severity) =>
    _get(`/shops/${shop}/audit/issues${severity ? `?severity=${severity}` : ''}`),
  getScore: (shop) => _get(`/shops/${shop}/audit/score`),
  getMetaSuggestions: (shop) => _get(`/shops/${shop}/suggestions/meta`),
  applyMeta: (shop, updates, dryRun = true) =>
    _post(`/shops/${shop}/apply/meta?dry_run=${dryRun}`, updates),
  getFaq: (lang = 'fr') => _get(`/help/faq?lang=${lang}`),
}
