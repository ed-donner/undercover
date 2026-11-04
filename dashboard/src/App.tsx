import { ClaimPage } from "./ClaimPage";
import { useHash } from "./hooks";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";

const INSTRUCTIONS = "#/instructions";

export function App() {
  const hash = useHash();
  return (
    <>
      <header className="header">
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden="true" />
          UnderCover
        </a>
        <span className="tagline">Travel Insurance claims</span>
        <nav aria-label="Main">
          <a href="#/" aria-current={isQueue(hash) ? "page" : undefined}>
            Queue
          </a>
          <a
            href={INSTRUCTIONS}
            aria-current={hash === INSTRUCTIONS ? "page" : undefined}
          >
            Agent instructions
          </a>
        </nav>
      </header>
      <main className="page">{page(hash)}</main>
    </>
  );
}

function isQueue(hash: string) {
  return hash === "" || hash === "#/";
}

function page(hash: string) {
  if (isQueue(hash)) return <QueuePage />;
  if (hash === INSTRUCTIONS) return <InstructionsPage />;
  const claim = /^#\/claims\/([\w-]+)$/.exec(hash);
  if (claim) return <ClaimPage key={claim[1]} claimId={claim[1]} />;
  return (
    <>
      <h1>Page not found</h1>
      <p>
        <a href="#/">Go to the claims queue</a>
      </p>
    </>
  );
}
