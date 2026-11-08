import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '../SeverityBadge';
import { BasisLabel } from '../BasisLabel';
import { VerdictBadge } from '../VerdictBadge';

describe('Status and Verdict Badges', () => {
  it('renders SeverityBadge with accessible text and shape for high severity', () => {
    render(<SeverityBadge severity="high" />);
    const badge = screen.getByLabelText(/high severity/i);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('High Severity');
    expect(badge).toHaveClass('text-red-800');
  });

  it('renders BasisLabel distinguishing rule-based from advisory AI', () => {
    const { rerender } = render(<BasisLabel basis="rule_based" />);
    expect(screen.getByText('Rule-based')).toBeInTheDocument();

    rerender(<BasisLabel basis="ai_assisted" />);
    expect(screen.getByText('AI-assisted (Advisory)')).toBeInTheDocument();
  });

  it('renders VerdictBadge with all four required claim verdicts', () => {
    const { rerender } = render(<VerdictBadge verdict="supported" />);
    expect(screen.getByText(/supported by approved source/i)).toBeInTheDocument();

    rerender(<VerdictBadge verdict="contradicted" />);
    expect(screen.getByText(/contradicted by approved source/i)).toBeInTheDocument();

    rerender(<VerdictBadge verdict="unsupported" />);
    expect(screen.getByText(/unsupported by approved source/i)).toBeInTheDocument();

    rerender(<VerdictBadge verdict="needs_human_review" />);
    expect(screen.getByText(/needs human review/i)).toBeInTheDocument();
  });
});
