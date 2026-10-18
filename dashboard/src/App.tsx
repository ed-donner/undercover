import { health } from "./api";
import { Queue } from "./Queue";
import { useRoute } from "./route";
import { usePolled } from "./usePolled";

const HEALTH_MS = 10000;

export function App() {
  const route = useRoute();
  const { data, error } = usePolled(health, HEALTH_MS);
  let backend = "checking";
  if (data) backend = "up";
  else if (error) backend = "down";

  return (
    <>
      <header className="header">
        <a className="brand" href="#/">
          UnderCover
        </a>
        <span className="mono backend">Backend: {backend}</span>
      </header>
      <main>{route.name === "queue" ? <Queue /> : <p>Page not found.</p>}</main>
    </>
  );
}
