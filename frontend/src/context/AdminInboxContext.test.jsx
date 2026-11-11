import { act } from "react";
import { createRoot } from "react-dom/client";
import { useContext } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ role: "admin", get: vi.fn() }));
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { id: mocks.role, role: mocks.role } }),
}));
vi.mock("@/lib/api", () => ({ default: { get: mocks.get } }));
import { AdminInboxContext, AdminInboxProvider } from "./AdminInboxContext";
import ChatUnread from "@/components/ChatUnread";
import ApprovalBadge from "@/components/ApprovalBadge";

global.IS_REACT_ACT_ENVIRONMENT = true;
describe("shared admin inbox", () => {
  let root;
  afterEach(async () => {
    if (root) await act(async () => root.unmount());
    root = null;
    vi.restoreAllMocks();
    mocks.get.mockReset();
  });
  for (const role of ["admin", "owner"])
    it(`${role}: shares requests across badges and keeps counts on temporary failure`, async () => {
      mocks.role = role;
      Object.defineProperty(document, "hidden", {
        configurable: true,
        value: false,
      });
      let chat = 4,
        approvals = 2,
        failure = false,
        context;
      mocks.get.mockImplementation(async (path) => {
        if (failure) throw new Error("offline");
        return { data: { count: path === "/chat/unread" ? chat : approvals } };
      });
      function Read() {
        context = useContext(AdminInboxContext);
        return (
          <>
            <ChatUnread />
            <ApprovalBadge />
          </>
        );
      }
      const container = document.createElement("div");
      root = createRoot(container);
      await act(async () =>
        root.render(
          <AdminInboxProvider>
            <Read />
          </AdminInboxProvider>,
        ),
      );
      expect(mocks.get.mock.calls.map((c) => c[0])).toEqual(
        role === "owner"
          ? ["/chat/unread", "/approvals/pending-count"]
          : ["/chat/unread"],
      );
      expect(context.chat).toBe(4);
      expect(context.approvals).toBe(role === "owner" ? 2 : 0);
      failure = true;
      await act(async () => context.refresh());
      expect(context.error).toBe(true);
      expect(context.chat).toBe(4);
      failure = false;
      chat = 0;
      approvals = 0;
      await act(async () =>
        window.dispatchEvent(new Event("big-mobile-chat-read")),
      );
      expect(context.chat).toBe(0);
      expect(context.approvals).toBe(0);
      expect(context.error).toBe(false);
      expect(container.textContent).toBe("");
    });
});
