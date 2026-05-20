import { useParams } from "react-router-dom";

export default function TaskDetailPage() {
  const { id } = useParams();
  return (
    <div>
      <h1>Task Detail</h1>
      <p>Task ID: {id}</p>
      <p>M0 placeholder</p>
    </div>
  );
}
