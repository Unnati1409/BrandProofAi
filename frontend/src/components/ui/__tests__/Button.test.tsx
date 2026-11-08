import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '../Button';

describe('Button Component', () => {
  it('renders children with default primary styles', () => {
    render(<Button>Submit Review</Button>);
    const button = screen.getByRole('button', { name: /submit review/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass('bg-surface-900');
  });

  it('handles disabled state correctly', () => {
    render(<Button disabled>Approve</Button>);
    const button = screen.getByRole('button', { name: /approve/i });
    expect(button).toBeDisabled();
    expect(button).toHaveClass('disabled:opacity-50');
  });

  it('renders loading spinner and disables button when isLoading is true', () => {
    render(<Button isLoading>Saving</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });
});
