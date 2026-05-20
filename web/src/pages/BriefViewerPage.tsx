import { useParams } from "react-router-dom";

export default function BriefViewerPage() {
  const { id } = useParams();
  return (
    <div>
      <h1>Brief Viewer</h1>
      <p>Task ID: {id}</p>
      <p>M0 placeholder</p>
    </div>
  );
}
