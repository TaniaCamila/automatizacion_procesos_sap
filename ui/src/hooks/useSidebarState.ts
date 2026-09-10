import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "cbo-ui.sidebar-collapsed";
const NOTEBOOK_BREAKPOINT = 1280;

function getInitialState() {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored !== null) return stored === "true";
  return window.innerWidth <= NOTEBOOK_BREAKPOINT;
}

export function useSidebarState() {
  const [collapsed, setCollapsed] = useState(getInitialState);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  const toggle = useCallback(() => {
    setCollapsed((current) => !current);
  }, []);

  return { collapsed, toggle };
}
