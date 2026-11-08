/**
 * BrandProof AI — Centralised API client.
 *
 * Every frontend fetch to the FastAPI backend MUST use `apiFetch()` from this
 * module.  This ensures:
 *   1. The correct backend base URL is always used (never the Vite dev server).
 *   2. The Supabase JWT is attached as a Bearer token.
 *   3. The active workspace ID is sent via the X-Workspace-ID header.
 *   4. Errors are surfaced consistently.
 */

import { supabase } from './supabase';

/**
 * Resolved once at module load time from the Vite env var, with a sensible
 * localhost fallback for development.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Wrapper around the native `fetch` that automatically:
 *   • Prepends the backend base URL to the given path.
 *   • Attaches the current Supabase session token as `Authorization: Bearer …`.
 *   • Sends the active workspace ID in the `X-Workspace-ID` header.
 *
 * Usage:
 * ```ts
 * const res = await apiFetch('/api/v1/workspaces');
 * ```
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  // Attach Supabase JWT — prefer the live session token so it auto-refreshes.
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  } catch {
    // If the session can't be retrieved, fall back to any stored token.
    const stored = localStorage.getItem('brandproof_token');
    if (stored) {
      headers['Authorization'] = `Bearer ${stored}`;
    }
  }

  // Attach workspace context.
  const wsId = localStorage.getItem('brandproof_active_workspace_id');
  if (wsId) {
    headers['X-Workspace-ID'] = wsId;
  }

  return fetch(`${API_BASE_URL}${path}`, { ...options, headers });
}

