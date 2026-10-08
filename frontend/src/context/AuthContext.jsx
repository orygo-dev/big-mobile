import { createContext, useContext, useEffect, useState } from "react";
import api, { setToken, clearToken, errMsg } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, object = user
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const expired = () => {clearToken(); setUser(false);};
    window.addEventListener('big-mobile-session-expired', expired);
    api.get("/auth/me")
      .then(({ data }) => setUser(data))
      .catch((e) => { if ([401, 403].includes(e.response?.status)) {clearToken(); setUser(false);} else setError(errMsg(e)); })
      .finally(() => setLoading(false));
    return () => window.removeEventListener('big-mobile-session-expired', expired);
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    if (data.token) setToken(data.token); else clearToken();
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    await api.post("/auth/logout");
    clearToken(); setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, loading }}>
      {error ? <div role="alert" className="min-h-screen flex flex-col items-center justify-center p-6 text-center gap-4"><p>{error}</p><button className="brand-action rounded-xl p-3" onClick={() => window.location.reload()}>Coba lagi</button></div> : children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
