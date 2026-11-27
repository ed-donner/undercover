import { ClaimPage } from "./ClaimPage";
import { useRoute } from "./format";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function Page({ route }: Readonly<{ route: string }>) {
  const claim = /^\/claims\/([\w-]+)$/.exec(route)?.[1];
  if (claim) return <ClaimPage claimId={claim} key={claim} />;
  if (route === "/instructions") return <Instructions />;
  return <Queue />;
}

export function App() {
  const route = useRoute();
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">
          UnderCover
        </a>
        <span className="tagline">Claims, handled</span>
        <nav aria-label="Main">
          <a href="#/" aria-current={route === "/" ? "page" : undefined}>
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route === "/instructions" ? "page" : undefined}
          >
            Agent instructions
          </a>
        </nav>
      </header>
      <main>
        <Page route={route} />
      </main>
    </>
  );
}
