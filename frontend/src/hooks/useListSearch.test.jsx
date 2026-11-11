import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useNavigate, useLocation } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { useListSearch, useCreateIntent } from "./useListSearch";

global.IS_REACT_ACT_ENVIRONMENT = true;
describe("header navigation reuses list and create flows", () => {
  it("updates the same list from URL search and consumes create without reopening the form", async () => {
    const container = document.createElement("div"),
      root = createRoot(container);
    let navigate,
      search,
      setSearch,
      location,
      opens = 0;
    function Page() {
      navigate = useNavigate();
      location = useLocation();
      [search, setSearch] = useListSearch();
      useCreateIntent(() => {
        opens++;
      });
      return <p>{search}</p>;
    }
    await act(async () =>
      root.render(
        <MemoryRouter
          initialEntries={["/admin/akun?search=awal&create=1&status=aktif"]}
        >
          <Page />
        </MemoryRouter>,
      ),
    );
    expect(search).toBe("awal");
    expect(opens).toBe(1);
    expect(location.search).toContain("status=aktif");
    expect(location.search).not.toContain("create");
    await act(async () => setSearch("diketik"));
    expect(opens).toBe(1);
    await act(async () => navigate("/admin/akun?search=baru"));
    expect(search).toBe("baru");
    expect(opens).toBe(1);
    await act(async () => navigate("/admin/akun?create=1"));
    expect(search).toBe("");
    expect(opens).toBe(2);
    await act(async () => root.unmount());
  });
});
