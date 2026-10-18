import { health } from "./api";
import { ClaimView } from "./ClaimView";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";
import { type Route, useRoute } from "./route";
import { usePolled } from "./usePolled";

const HEALTH_MS = 10000;

function Page({ route }: Readonly<{ route: Route }>) {
  switch (route.name) {
    case "queue":
      return <Queue />;
    case "claim":
      return <ClaimView id={route.id} />;
    case "instructions":
      return <Instructions />;
    default:
      return <p>Page not found.</p>;
  }
}

export function App() {
  const route = useRoute();
  const { data, error } = usePolled(health, HEALTH_MS);
  let backend = "checking";
  if (data) backend = "up";
  else if (error) backend = "down";

  return (
    <>
      <header className="header">
        <nav className="nav">
          <a className="brand" href="#/">
            UnderCover
          </a>
          <a href="#/">Queue</a>
          <a href="#/instructions">Instructions</a>
        </nav>
        <span className="mono backend">Backend: {backend}</span>
      </header>
      <main>
        <Page route={route} />
      </main>
    </>
  );
}
