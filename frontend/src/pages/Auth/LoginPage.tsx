import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button, Input } from '../../components/ui';
import { ShieldCheck, AlertCircle } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { apiFetch } from '../../lib/api';

interface LoginPageProps {
  onNavigateToRegister?: () => void;
  onLoginSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onNavigateToRegister,
  onLoginSuccess,
}) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please enter both your work email and password.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      // 1. Authenticate with Supabase Auth
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (error || !data.session) {
        setErrorMessage(error?.message || 'Authentication failed. Please verify your credentials.');
        setIsLoading(false);
        return;
      }

      const accessToken = data.session.access_token;

      // 2. Fetch full verified profile with workspace memberships from FastAPI
      const profileRes = await apiFetch('/api/v1/auth/me', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!profileRes.ok) {
        throw new Error('Failed to retrieve user profile from application backend.');
      }

      const profile = await profileRes.json();
      login(accessToken, profile);
      onLoginSuccess?.();
    } catch (err: any) {
      setErrorMessage(err.message || 'An unexpected error occurred during login.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoFill = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('DemoPass123!');
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-surface-50 p-4">
      <div className="w-full max-w-md bg-white border border-surface-200 rounded-lg shadow-subtle p-8">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-10 h-10 rounded-md bg-surface-900 text-white flex items-center justify-center mb-3">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-surface-900">
            BrandProof AI
          </h1>
          <p className="text-xs text-surface-500 mt-1">
            Enterprise Pre-Publication Editorial Governance
          </p>
        </div>

        {errorMessage && (
          <div
            className="mb-5 p-3 rounded bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-2"
            role="alert"
          >
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
            <div className="flex-1 font-medium">{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Work Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@company.com"
            required
            autoComplete="email"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            autoComplete="current-password"
          />

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isLoading}
            variant="primary"
          >
            Sign in to Workspace
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-surface-100 flex flex-col gap-3">
          <div className="text-xs text-surface-500 text-center">
            Don&apos;t have an account?{' '}
            <button
              type="button"
              onClick={onNavigateToRegister}
              className="text-surface-900 font-semibold hover:underline"
            >
              Register here
            </button>
          </div>

          <div className="p-2.5 rounded bg-surface-50 border border-surface-200 text-2xs text-surface-600">
            <p className="font-semibold text-surface-700 mb-1">Demo Quick-Fill:</p>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => handleDemoFill('admin@aurahealth.demo')}
                className="px-2 py-0.5 rounded border border-surface-300 bg-white hover:bg-surface-100 text-surface-800 font-mono transition-colors"
              >
                admin@aurahealth.demo
              </button>
              <button
                type="button"
                onClick={() => handleDemoFill('creator@aurahealth.demo')}
                className="px-2 py-0.5 rounded border border-surface-300 bg-white hover:bg-surface-100 text-surface-800 font-mono transition-colors"
              >
                creator@aurahealth.demo
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
