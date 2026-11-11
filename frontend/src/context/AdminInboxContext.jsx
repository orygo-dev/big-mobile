import { createContext, useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export const AdminInboxContext = createContext(null);

// One subscription for the sidebar and header; existing events remain supported.
export function AdminInboxProvider({ children }) {
  const { user } = useAuth();
  const owner = user?.role === "owner";
  const [counts, setCounts] = useState({
    chat: 0,
    approvals: 0,
    loading: true,
    error: false,
  });
  const previous = useRef(null),
    controller = useRef(null),
    alive = useRef(false);
  const refresh = useCallback(async () => {
    if (document.hidden || !alive.current) return;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    const paths = [
      "/chat/unread",
      ...(owner ? ["/approvals/pending-count"] : []),
    ];
    const results = await Promise.allSettled(
      paths.map((path) => api.get(path, { signal: request.signal })),
    );
    if (!alive.current || request.signal.aborted) return;
    const read = (result) => {
      const value =
        result?.status === "fulfilled" ? Number(result.value.data?.count) : NaN;
      return Number.isSafeInteger(value) && value >= 0 ? value : null;
    };
    const chat = read(results[0]),
      approvals = owner ? read(results[1]) : 0;
    if (chat !== null) {
      if (previous.current !== null && chat > previous.current)
        toast.info("Ada pesan chat baru. Buka menu Chat untuk membaca.", {
          id: "chat-new-message",
        });
      previous.current = chat;
    }
    setCounts((old) => ({
      chat: chat ?? old.chat,
      approvals: approvals ?? old.approvals,
      loading: false,
      error: chat === null || approvals === null,
    }));
  }, [owner, user?.id]);
  useEffect(() => {
    alive.current = true;
    previous.current = null;
    setCounts({ chat: 0, approvals: 0, loading: true, error: false });
    refresh();
    const timer = setInterval(refresh, 15000);
    window.addEventListener("big-mobile-chat-read", refresh);
    window.addEventListener("big-mobile-approval-changed", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      alive.current = false;
      controller.current?.abort();
      clearInterval(timer);
      window.removeEventListener("big-mobile-chat-read", refresh);
      window.removeEventListener("big-mobile-approval-changed", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [refresh]);
  return (
    <AdminInboxContext.Provider value={{ ...counts, refresh }}>
      {children}
    </AdminInboxContext.Provider>
  );
}
