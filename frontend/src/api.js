const BASE = '/api'

async function _get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

async function _post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  applyMeta: (shop, updates, dryRun = true) =>
    _post(`/shops/${shop}/apply/meta?dry_run=${dryRun}`, updates),
}
