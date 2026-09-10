import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Moves keyboard/screen-reader focus to content after client-side navigation. */
export function RouteFocusManager() {
  const { pathname } = useLocation();

  useEffect(() => {
    const main = document.getElementById("main-content");
    main?.focus({ preventScroll: true });
  }, [pathname]);

  return null;
}
