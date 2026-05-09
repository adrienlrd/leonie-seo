import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('../../api', () => ({
  api: {
    getMetaSuggestions: vi.fn(),
    applyMeta: vi.fn(),
  },
}))

import { api } from '../../api'
import MetaApplyPanel from '../MetaApplyPanel'

const SUGGESTIONS = [
  {
    product_id: 'gid://shopify/Product/1',
    product_title: 'Bol Premium',
    suggested_title: 'Bol Premium pour chien — Léonie Delacroix',
    suggested_description: 'Bol design en céramique pour chien, fabriqué en France.',
  },
]

beforeEach(() => {
  api.getMetaSuggestions.mockResolvedValue(SUGGESTIONS)
  api.applyMeta.mockResolvedValue([{ status: 'preview', detail: 'preview ok', product_id: 'gid://shopify/Product/1' }])
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('MetaApplyPanel', () => {
  it('shows the empty state when no shop is selected', () => {
    render(<MetaApplyPanel shop={null} />)
    expect(screen.getByText(/Sélectionnez une boutique/)).toBeInTheDocument()
  })

  it('loads and displays suggestions from the API', async () => {
    render(<MetaApplyPanel shop="test.myshopify.com" />)
    await waitFor(() => expect(screen.getByText('Bol Premium')).toBeInTheDocument())
    expect(api.getMetaSuggestions).toHaveBeenCalledWith('test.myshopify.com')
  })

  it('shows the empty hint when no suggestions are returned', async () => {
    api.getMetaSuggestions.mockResolvedValue([])
    render(<MetaApplyPanel shop="test.myshopify.com" />)
    await waitFor(() => expect(screen.getByText(/Aucune suggestion disponible/)).toBeInTheDocument())
  })

  it('calls applyMeta with dry_run=true when previewing', async () => {
    render(<MetaApplyPanel shop="test.myshopify.com" />)
    await waitFor(() => screen.getByText('Bol Premium'))
    fireEvent.click(screen.getByRole('button', { name: /Prévisualiser/ }))
    await waitFor(() => expect(api.applyMeta).toHaveBeenCalled())
    expect(api.applyMeta).toHaveBeenCalledWith(
      'test.myshopify.com',
      expect.any(Array),
      true,
    )
  })

  it('calls applyMeta with dry_run=false when applying', async () => {
    api.applyMeta.mockResolvedValue([{ status: 'applied', product_id: 'gid://shopify/Product/1' }])
    render(<MetaApplyPanel shop="test.myshopify.com" />)
    await waitFor(() => screen.getByText('Bol Premium'))
    fireEvent.click(screen.getByRole('button', { name: /Appliquer sur Shopify/ }))
    await waitFor(() => expect(api.applyMeta).toHaveBeenCalledWith(
      'test.myshopify.com',
      expect.any(Array),
      false,
    ))
  })
})
