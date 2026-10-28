import { ClaimPage } from "./ClaimPage";
import { type Route, useRoute, useTheme } from "./hooks";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function Page({ route }: Readonly<{ route: Route }>) {
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "instructions":
      return <Instructions />;
    case "queue":
      return <Queue />;
  }
}

export function App() {
  const route = useRoute();
  const { theme, toggle } = useTheme();
  return (
    <div className="app">
      <header className="top">
        <a className="brand" href="#/">
          UnderCover <span className="tagline">Claims</span>
        </a>
        <nav aria-label="Main">
          <a
            href="#/"
            aria-current={route.page === "queue" ? "page" : undefined}
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.page === "instructions" ? "page" : undefined}
          >
            Agent instructions
          </a>
          <button
            type="button"
            className="theme-toggle"
            aria-pressed={theme === "dark"}
            onClick={toggle}
          >
            Dark mode
          </button>
        </nav>
      </header>
      <main>
        <Page route={route} />
      </main>
    </div>
  );
}
