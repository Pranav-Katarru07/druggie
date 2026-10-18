import { NavLink, Outlet } from "react-router";
import { usePatients } from "../data/patientsContext";
import "./AppLayout.css";

export default function AppLayout() {
  const data = usePatients();

  return (
    <div className="shell">
      <header className="shell-header">
        <span className="wordmark">Druggie</span>
        <nav className="nav" aria-label="Pages">
          <NavLink to="/review">Review</NavLink>
          <NavLink to="/patients">Patients</NavLink>
          <NavLink to="/insights">Insights</NavLink>
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
