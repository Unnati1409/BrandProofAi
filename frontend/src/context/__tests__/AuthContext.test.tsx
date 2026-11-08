import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../AuthContext';

const TestAuthConsumer: React.FC = () => {
  const { token, user, login, logout } = useAuth();
  return (
    <div>
      <div data-testid="token">{token || 'no-token'}</div>
      <div data-testid="user-email">{user?.email || 'no-email'}</div>
      <button
        onClick={() =>
          login('test-jwt-token-xyz', {
            id: 'usr_123',
            email: 'admin@aurahealth.demo',
            full_name: 'Admin User',
            workspaces: [
              {
                workspace_id: 'ws_1',
                workspace_name: 'AuraHealth',
                workspace_slug: 'aurahealth',
                roles: ['admin'],
              },
            ],
          })
        }
      >
        Trigger Login
      </button>
      <button onClick={logout}>Trigger Logout</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('initializes with null state when localStorage is empty', () => {
    render(
      <AuthProvider>
        <TestAuthConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId('token')).toHaveTextContent('no-token');
    expect(screen.getByTestId('user-email')).toHaveTextContent('no-email');
  });

  it('updates state and persists token on login', () => {
    render(
      <AuthProvider>
        <TestAuthConsumer />
      </AuthProvider>
    );

    act(() => {
      screen.getByText('Trigger Login').click();
    });

    expect(screen.getByTestId('token')).toHaveTextContent('test-jwt-token-xyz');
    expect(screen.getByTestId('user-email')).toHaveTextContent('admin@aurahealth.demo');
    expect(localStorage.getItem('brandproof_token')).toBe('test-jwt-token-xyz');
  });

  it('clears state and removes token on logout', () => {
    localStorage.setItem('brandproof_token', 'existing-token');
    localStorage.setItem(
      'brandproof_user',
      JSON.stringify({
        id: 'usr_1',
        email: 'creator@aurahealth.demo',
        full_name: 'Creator',
        workspaces: [],
      })
    );

    render(
      <AuthProvider>
        <TestAuthConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId('token')).toHaveTextContent('existing-token');
    expect(screen.getByTestId('user-email')).toHaveTextContent('creator@aurahealth.demo');

    act(() => {
      screen.getByText('Trigger Logout').click();
    });

    expect(screen.getByTestId('token')).toHaveTextContent('no-token');
    expect(screen.getByTestId('user-email')).toHaveTextContent('no-email');
    expect(localStorage.getItem('brandproof_token')).toBeNull();
  });
});
