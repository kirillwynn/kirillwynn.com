// frontend/src/lib/auth.ts
// Global authentication state + helpers.
// - Keeps track of current user
// - Knows whether auth check is in progress
// - Central place for login/logout logic

import { api, type ApiUser } from "./api";

export type AuthState = {
  loading: boolean;
  authenticated: boolean;
  user: ApiUser | null;
};

let state: AuthState = {
  loading: true,
  authenticated: false,
  user: null,
};

// Subscribers (simple pub/sub, no framework lock-in)
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

export const auth = {
  // Read current state
  getState(): AuthState {
    return state;
  },

  // Subscribe to state changes
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  // Initial session check: call once on app start
  async init() {
    state = { ...state, loading: true };
    notify();

    try {
      const res = await api.me();

      if (res.authenticated) {
        state = {
          loading: false,
          authenticated: true,
          user: res.user,
        };
      } else {
        state = {
          loading: false,
          authenticated: false,
          user: null,
        };
      }
    } catch {
      // Any error here means "treat as logged out"
      // (network error, 500, invalid session, etc.)
      state = {
        loading: false,
        authenticated: false,
        user: null,
      };
    }

    notify();
  },

  // Login via API
  async login(email: string, password: string) {
    const res = await api.login(email, password);

    if (!res.ok) {
      // Preserve backend error message
      throw new Error(res.error);
    }

    state = {
      loading: false,
      authenticated: true,
      user: res.user,
    };

    notify();
  },

  // Logout via API
  async logout() {
    await api.logout();

    state = {
      loading: false,
      authenticated: false,
      user: null,
    };

    notify();
  },
};
