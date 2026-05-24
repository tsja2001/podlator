import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage";
import QueuePage from "./pages/QueuePage";
import TaskDetailPage from "./pages/TaskDetailPage";
import BriefViewerPage from "./pages/BriefViewerPage";

function Nav() {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <nav
      style={{
        display: "flex",
        gap: 16,
        padding: "12px 24px",
        borderBottom: "1px solid var(--border)",
        alignItems: "center",
      }}
    >
      <Link
        to="/"
        style={{
          fontWeight: 700,
          fontSize: 16,
          color: "var(--text-h)",
          textDecoration: "none",
        }}
      >
        Podlator
      </Link>
      <div style={{ flex: 1 }} />
      <Link
        to="/"
        style={{
          color: isActive("/") ? "var(--accent)" : "var(--text)",
          textDecoration: "none",
          fontSize: 14,
          fontWeight: isActive("/") ? 600 : 400,
        }}
      >
        提交
      </Link>
      <Link
        to="/queue"
        style={{
          color: location.pathname.startsWith("/queue") ? "var(--accent)" : "var(--text)",
          textDecoration: "none",
          fontSize: 14,
          fontWeight: location.pathname.startsWith("/queue") ? 600 : 400,
        }}
      >
        队列
      </Link>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main style={{ padding: "0 24px" }}>
        <Routes>
          <Route path="/" element={<SubmitPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/tasks/:id" element={<TaskDetailPage />} />
          <Route path="/tasks/:id/brief" element={<BriefViewerPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
