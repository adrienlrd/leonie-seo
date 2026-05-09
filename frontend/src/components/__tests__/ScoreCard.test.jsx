import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScoreCard from '../ScoreCard'

describe('ScoreCard', () => {
  it('renders the score label', () => {
    render(<ScoreCard score={{ total: 83.9, components: {} }} status="ok" />)
    expect(screen.getByText('Score SEO global')).toBeInTheDocument()
    expect(screen.getByText('84')).toBeInTheDocument()
  })

  it('shows a placeholder while loading', () => {
    const { container } = render(<ScoreCard score={null} status="loading" />)
    expect(container.querySelector('.value').textContent).toBe('…')
  })

  it('renders nothing when there is no score and not loading', () => {
    const { container } = render(<ScoreCard score={null} status="ok" />)
    expect(container.firstChild).toBeNull()
  })

  it('uses score-good class when score >= 75', () => {
    const { container } = render(<ScoreCard score={{ total: 80, components: {} }} status="ok" />)
    expect(container.querySelector('.score-good')).not.toBeNull()
  })

  it('uses score-bad class when score < 50', () => {
    const { container } = render(<ScoreCard score={{ total: 30, components: {} }} status="ok" />)
    expect(container.querySelector('.score-bad')).not.toBeNull()
  })
})
