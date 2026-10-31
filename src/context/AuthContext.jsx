import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    apiRequest("/auth/me")
      .then((data) => active && setCurrentUser(data.user))
      .catch(() => active && setCurrentUser(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  async function login(email, password) {
    try {
      const data = await apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setCurrentUser(data.user);
      return { ok: true, user: data.user };
    } catch (error) {
      return { ok: false, error: error.message || "Unable to connect to the server." };
    }
  }

  async function register(form) {
    try {
      const data = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({ name: form.name, email: form.email, password: form.password, role: form.role }),
      });
      return { ok: true, user: data.user };
    } catch (error) {
      return { ok: false, error: error.message || "Unable to connect to the server." };
    }
  }

  async function logout() {
    try { await apiRequest("/auth/logout", { method: "POST" }); }
    finally { setCurrentUser(null); }
  }

  const value = useMemo(() => ({ currentUser, loading, login, register, logout }), [currentUser, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// oxlint-disable-next-line react/only-export-components -- Provider and hook intentionally share one context module.
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
