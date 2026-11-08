import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button, Input } from '../../components/ui';
import { ShieldCheck, AlertCircle, CheckCircle2 } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { apiFetch } from '../../lib/api';

interface RegisterPageProps {
  onNavigateToLogin?: () => void;
  onRegisterSuccess?: () => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({
  onNavigateToLogin,
  onRegisterSuccess,
}) => {
  const { login } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !email || !password) {
      setErrorMessage('All fields are required.');
      return;
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      // 1. Register user via Supabase Auth
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim(),
          },
        },
      });

      if (error) {
        setErrorMessage(error.message || 'Registration failed. Please try again.');
        setIsLoading(false);
        return;
      }

      if (data.session) {
        // Session active immediately (auto-confirm enabled)
        setSuccessMessage('Account created successfully! Logging you in...');
        const accessToken = data.session.access_token;

        // Fetch user profile from FastAPI backend
        const profileRes = await apiFetch('/api/v1/auth/me', {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (profileRes.ok) {
          const profile = await profileRes.json();
          login(accessToken, profile);
          onRegisterSuccess?.();
        } else {
          onNavigateToLogin?.();
        }
      } else {
        // Confirmation email sent
        setSuccessMessage(
          'Account created! A confirmation email has been sent. Please verify your email before logging in.'
        );
        setTimeout(() => {
          onNavigateToLogin?.();
        }, 3000);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-surface-50 p-4">
      <div className="w-full max-w-md bg-white border border-surface-200 rounded-lg shadow-subtle p-8">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-10 h-10 rounded-md bg-surface-900 text-white flex items-center justify-center mb-3">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-surface-900">
            Create an Account
          </h1>
          <p className="text-xs text-surface-500 mt-1">
            BrandProof AI — Editorial Governance Platform
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

        {successMessage && (
          <div
            className="mb-5 p-3 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2"
            role="status"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
            <div className="flex-1 font-medium">{successMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Full Name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jane Doe"
            required
            autoComplete="name"
          />

          <Input
            label="Work Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="jane@company.com"
            required
            autoComplete="email"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            required
            helperText="Minimum 8 characters"
            autoComplete="new-password"
          />

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isLoading}
            variant="primary"
          >
            Create Account & Continue
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-surface-100 text-center">
          <p className="text-xs text-surface-500">
            Already have an account?{' '}
            <button
              type="button"
              onClick={onNavigateToLogin}
              className="text-surface-900 font-semibold hover:underline"
            >
              Sign in
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};
