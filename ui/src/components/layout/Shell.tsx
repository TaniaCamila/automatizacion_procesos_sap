import { Outlet } from "react-router-dom";
import { useSidebarState } from "../../hooks/useSidebarState";
import { RouteFocusManager } from "../navigation/RouteFocusManager";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function Shell() {
  const { collapsed, toggle } = useSidebarState();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div className="app-shell__main">
        <TopBar />
        <RouteFocusManager />
        <main
          id="main-content"
          className="app-shell__content"
          tabIndex={-1}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
