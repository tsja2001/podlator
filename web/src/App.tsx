import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage";
import QueuePage from "./pages/QueuePage";
import TaskDetailPage from "./pages/TaskDetailPage";
import BriefViewerPage from "./pages/BriefViewerPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #ccc" }}>
        <Link to="/" style={{ marginRight: "1rem" }}>
          Submit
        </Link>
        <Link to="/queue">Queue</Link>
      </nav>
      <main style={{ padding: "1rem" }}>
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
