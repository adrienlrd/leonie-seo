import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import IssuesList from '../IssuesList'

const ISSUES = [
  { issue_type: 'missing_meta_title', severity: 'critical', resource_title: 'Bol Premium', detail: 'Title is missing.' },
  { issue_type: 'too_short_meta_title', severity: 'high', resource_title: 'Harnais Cuir', detail: 'Title too short.' },
  { issue_type: 'missing_alt_text', severity: 'high', resource_title: 'Image — Bol Premium', detail: 'No alt text.' },
]

describe('IssuesList', () => {
  it('renders all issues by default', () => {
    render(<IssuesList issues={ISSUES} loading={false} error={null} />)
    expect(screen.getByText(/Issues SEO \(3\)/)).toBeInTheDocument()
    expect(screen.getByText('Bol Premium')).toBeInTheDocument()
    expect(screen.getByText('Harnais Cuir')).toBeInTheDocument()
  })

  it('filters issues by severity when a filter button is clicked', () => {
    render(<IssuesList issues={ISSUES} loading={false} error={null} />)
    fireEvent.click(screen.getByRole('button', { name: 'critical' }))
    expect(screen.getByText(/Issues SEO \(1\)/)).toBeInTheDocument()
    expect(screen.queryByText('Harnais Cuir')).not.toBeInTheDocument()
  })

  it('shows the empty state when there are no issues', () => {
    render(<IssuesList issues={[]} loading={false} error={null} />)
    expect(screen.getByText(/Aucune issue/)).toBeInTheDocument()
  })

  it('displays a loading message', () => {
    render(<IssuesList issues={[]} loading={true} error={null} />)
    expect(screen.getByText('Chargement…')).toBeInTheDocument()
  })

  it('shows the error banner when error prop is set', () => {
    render(<IssuesList issues={[]} loading={false} error="Boom" />)
    expect(screen.getByText('Boom')).toBeInTheDocument()
  })
})
