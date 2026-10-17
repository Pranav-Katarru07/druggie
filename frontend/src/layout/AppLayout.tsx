import { NavLink, Outlet } from "react-router";
import { usePatients } from "../data/patientsContext";
import "./AppLayout.css";

export default function AppLayout() {
  const data = usePatients();

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden>Rx</span>
          <div>
            <h1>Druggie</h1>
            <p>Draft evidence for physician review, not a final determination</p>
          </div>
        </div>
        <nav className="nav" aria-label="Pages">
          <NavLink to="/review">Review</NavLink>
          <NavLink to="/browse">Browse</NavLink>
        </nav>
      </header>

      <main className="shell-main">
        {data.status === "loading" && <p className="empty">Loading…</p>}
        {data.status === "error" && <p className="empty">{data.message}</p>}
        {data.status === "ready" && <Outlet />}
      </main>
    </div>
  );
}
