import { ClaimPage } from "./pages/ClaimPage";
import { Instructions } from "./pages/Instructions";
import { Queue } from "./pages/Queue";
import { useRoute } from "./router";

function Page() {
  const route = useRoute();
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "instructions":
      return <Instructions />;
    default:
      return <Queue />;
  }
}

export function App() {
  return (
    <>
      <nav className="top">
        <a href="#/" className="brand">
          UnderCover <span className="tagline">Claims desk</span>
        </a>
        <a href="#/">Queue</a>
        <a href="#/instructions">Agent instructions</a>
      </nav>
      <main>
        <Page />
      </main>
    </>
  );
}
