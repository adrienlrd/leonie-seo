import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'

beforeEach(() => {
  global.fetch = vi.fn()
})

afterEach(() => {
  vi.restoreAllMocks()
})

function _ok(body) {
  return Promise.resolve({
    ok: true,
    status: 200,
    text: () => Promise.resolve(''),
    json: () => Promise.resolve(body),
  })
}

function _err(status = 500, body = 'oops') {
  return Promise.resolve({
    ok: false,
    status,
    text: () => Promise.resolve(body),
    json: () => Promise.resolve({}),
  })
}

describe('api wrappers', () => {
  it('listShops calls GET /api/shops', async () => {
    fetch.mockReturnValue(_ok([{ shop: 'a.myshopify.com' }]))
    const result = await api.listShops()
    expect(fetch).toHaveBeenCalledWith('/api/shops', expect.objectContaining({ headers: {} }))
    expect(result).toEqual([{ shop: 'a.myshopify.com' }])
  })

  it('getIssues appends severity filter when provided', async () => {
    fetch.mockReturnValue(_ok([]))
    await api.getIssues('xyz.myshopify.com', 'critical')
    expect(fetch).toHaveBeenCalledWith(
      '/api/shops/xyz.myshopify.com/audit/issues?severity=critical',
      expect.anything(),
    )
  })

  it('getIssues omits the severity query when not provided', async () => {
    fetch.mockReturnValue(_ok([]))
    await api.getIssues('xyz.myshopify.com')
    expect(fetch).toHaveBeenCalledWith(
      '/api/shops/xyz.myshopify.com/audit/issues',
      expect.anything(),
    )
  })

  it('applyMeta posts with dry_run query param and JSON body', async () => {
    fetch.mockReturnValue(_ok([{ status: 'preview' }]))
    const updates = [{ product_id: 'gid://shopify/Product/1', title: 'X' }]
    await api.applyMeta('xyz.myshopify.com', updates, true)
    expect(fetch).toHaveBeenCalledWith(
      '/api/shops/xyz.myshopify.com/apply/meta?dry_run=true',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(updates),
      }),
    )
  })

  it('throws an Error with status code on non-2xx', async () => {
    fetch.mockReturnValue(_err(403, 'Forbidden'))
    await expect(api.listShops()).rejects.toThrow('403 Forbidden')
  })

  it('attaches Authorization header when window.shopify provides idToken', async () => {
    global.window = global.window || {}
    window.shopify = { idToken: vi.fn().mockResolvedValue('jwt-abc') }
    fetch.mockReturnValue(_ok([]))

    await api.listShops()

    expect(fetch).toHaveBeenCalledWith(
      '/api/shops',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer jwt-abc' }),
      }),
    )
    delete window.shopify
  })
})
