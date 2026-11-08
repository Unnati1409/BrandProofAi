import React, { createContext, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { apiFetch } from '../lib/api';

export interface WorkspaceMembership {
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  roles: string[];
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  created_at?: string;
  workspaces: WorkspaceMembership[];
}

interface AuthContextType {
  token: string | null;
  user: UserProfile | null;
  supabaseUser: User | null;
  session: Session | null;
  isLoading: boolean;
  login: (token: string, profile: UserProfile) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('brandproof_token'));
  const [user, setUser] = useState<UserProfile | null>(() => {
    const cached = localStorage.getItem('brandproof_user');
    return cached ? JSON.parse(cached) : null;
  });
  const [session, setSession] = useState<Session | null>(null);
  const [supabaseUser, setSupabaseUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchProfile = async (authToken: string) => {
    try {
      const res = await apiFetch('/api/v1/auth/me', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (res.ok) {
        const profile: UserProfile = await res.json();
        setUser(profile);
        localStorage.setItem('brandproof_user', JSON.stringify(profile));
      } else if (res.status === 401) {
        await logout();
      }
    } catch (err) {
      console.warn('[BrandProof AI] Could not refresh profile from backend:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // 1. Restore existing session on mount
    supabase.auth.getSession().then(({ data: { session: existingSession } }) => {
      if (existingSession) {
        setSession(existingSession);
        setToken(existingSession.access_token);
        setSupabaseUser(existingSession.user);
        localStorage.setItem('brandproof_token', existingSession.access_token);
        fetchProfile(existingSession.access_token);
      } else if (token) {
        // Fallback to cached token
        fetchProfile(token);
      } else {
        setIsLoading(false);
      }
    });

    // 2. Listen to live Supabase Auth state changes (token refresh, sign in, sign out)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, newSession) => {
      if (newSession) {
        setSession(newSession);
        setToken(newSession.access_token);
        setSupabaseUser(newSession.user);
        localStorage.setItem('brandproof_token', newSession.access_token);
        await fetchProfile(newSession.access_token);
      } else if (event === 'SIGNED_OUT') {
        setSession(null);
        setToken(null);
        setSupabaseUser(null);
        setUser(null);
        localStorage.removeItem('brandproof_token');
        localStorage.removeItem('brandproof_user');
        localStorage.removeItem('brandproof_active_workspace_id');
        setIsLoading(false);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const login = (newToken: string, newProfile: UserProfile) => {
    setToken(newToken);
    setUser(newProfile);
    localStorage.setItem('brandproof_token', newToken);
    localStorage.setItem('brandproof_user', JSON.stringify(newProfile));
  };

  const logout = async () => {
    setToken(null);
    setUser(null);
    setSession(null);
    setSupabaseUser(null);
    localStorage.removeItem('brandproof_token');
    localStorage.removeItem('brandproof_user');
    localStorage.removeItem('brandproof_active_workspace_id');
    try {
      await supabase.auth.signOut();
    } catch (err) {
      console.warn('[BrandProof AI] Error during Supabase signOut:', err);
    }
  };

  const refreshUser = async () => {
    if (token) {
      await fetchProfile(token);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        supabaseUser,
        session,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
