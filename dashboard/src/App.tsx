import { useEffect, useState } from "react";
import { ClaimView } from "./ClaimView";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("hashchange", update);
    };
  }, []);
  return hash;
}

function useHealth() {
  const [status, setStatus] = useState("checking");
  useEffect(() => {
    void fetch("/api/health")
      .then((response) => (response.ok ? "up" : "down"))
      .catch(() => "down")
      .then(setStatus);
  }, []);
  return status;
}

function Page({ hash }: Readonly<{ hash: string }>) {
  if (hash === "#/instructions") return <Instructions />;
  const claim = /^#\/claims\/(.+)$/.exec(hash);
  if (claim?.[1]) return <ClaimView key={claim[1]} claimId={claim[1]} />;
  return <Queue />;
}

export function App() {
  const hash = useHash();
  const health = useHealth();
  const onInstructions = hash === "#/instructions";

  return (
    <>
      <header className="header">
        <p className="brand">UnderCover</p>
        <span className="tagline">Claims desk</span>
        <nav className="nav">
          <a href="#/" aria-current={onInstructions ? undefined : "page"}>
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={onInstructions ? "page" : undefined}
          >
            Instructions
          </a>
          <span className="health">Backend: {health}</span>
        </nav>
      </header>
      <main>
        <Page hash={hash} />
      </main>
    </>
  );
}
