import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LoginPage } from '../Auth/LoginPage';
import { AuthProvider } from '../../context/AuthContext';

describe('LoginPage', () => {
  it('renders sign-in form with email and password inputs', () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    expect(screen.getByText('BrandProof AI')).toBeInTheDocument();
    expect(screen.getByLabelText(/work email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in to workspace/i })).toBeInTheDocument();
  });

  it('populates credentials when a demo quick-fill button is clicked', () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    const demoAdminBtn = screen.getByText('admin@aurahealth.demo');
    fireEvent.click(demoAdminBtn);

    const emailInput = screen.getByLabelText(/work email/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement;

    expect(emailInput.value).toBe('admin@aurahealth.demo');
    expect(passwordInput.value).toBe('DemoPass123!');
  });

  it('triggers register navigation callback when clicking register link', () => {
    const onNavigateToRegister = vi.fn();

    render(
      <AuthProvider>
        <LoginPage onNavigateToRegister={onNavigateToRegister} />
      </AuthProvider>
    );

    const registerBtn = screen.getByRole('button', { name: /register here/i });
    fireEvent.click(registerBtn);

    expect(onNavigateToRegister).toHaveBeenCalledTimes(1);
  });
});