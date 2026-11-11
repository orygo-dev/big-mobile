import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Links from the header reuse each page's existing search and validation flow.
export function useListSearch() {
  const [params] = useSearchParams();
  const fromUrl = params.get("search") || "";
  const [search, setSearch] = useState(fromUrl);
  useEffect(() => {
    setSearch(fromUrl);
  }, [fromUrl]);
  return [search, setSearch];
}

export function useCreateIntent(open) {
  const [params, setParams] = useSearchParams();
  const callback = useRef(open);
  useEffect(() => {
    callback.current = open;
  });
  useEffect(() => {
    if (params.get("create") !== "1") return;
    callback.current();
    const next = new URLSearchParams(params);
    next.delete("create");
    setParams(next, { replace: true });
  }, [params, setParams]);
}
