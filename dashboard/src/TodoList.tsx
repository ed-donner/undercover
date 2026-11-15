import type { Todo } from "./api";
import { Status } from "./Status";

export function TodoList({ todos }: Readonly<{ todos: Todo[] }>) {
  if (todos.length === 0) return <p className="muted">No plan yet.</p>;
  return (
    <ol className="todos" aria-label="To-do list">
      {todos.map((todo) => (
        <li key={todo.text}>
          <span className="mono">{todo.text}</span>
          <Status status={todo.status} />
        </li>
      ))}
    </ol>
  );
}
