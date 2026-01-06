// frontend/src/lib/AuthProvider.tsx
// React bridge for the auth singleton.
// - Subscribes to auth state
// - Triggers initial session check
// - Exposes auth state via context

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { auth, type AuthState } from "./auth";

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(auth.getState());

  useEffect(() => {
    // Subscribe to auth state changes
    const unsubscribe = auth.subscribe(() => {
      setState(auth.getState());
    });

    // Run initial session check once
    auth.init();

    return unsubscribe;
  }, []);

  return (
    <AuthContext.Provider value={state}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook for consuming auth state
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
