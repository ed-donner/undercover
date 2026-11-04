import { useHash } from "./hooks";
import { QueuePage } from "./QueuePage";

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
  return (
    <>
      <h1>Page not found</h1>
      <p>
        <a href="#/">Go to the claims queue</a>
      </p>
    </>
  );
}
