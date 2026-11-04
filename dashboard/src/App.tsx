import { useEffect, useState } from "react";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";

const CLAIM_ROUTE = /^#\/claims\/([\w-]+)$/;

function Page({ hash }: Readonly<{ hash: string }>) {
  const claimId = CLAIM_ROUTE.exec(hash)?.[1];
  if (claimId) return <ClaimPage claimId={claimId} />;
  if (hash === "#/instructions") return <InstructionsPage />;
  return <QueuePage />;
}

export function App() {
  const [status, setStatus] = useState("checking");
  const [hash, setHash] = useState(window.location.hash);

  useEffect(() => {
    void fetch("/api/health")
      .then((response) => (response.ok ? "up" : "down"))
      .catch(() => "down")
      .then(setStatus);
  }, []);

  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);

  return (
    <main>
      <header>
        <h1>UnderCover</h1>
        <nav>
          <a href="#/">Queue</a>
          <a href="#/instructions">Instructions</a>
        </nav>
        <p>Backend: {status}</p>
      </header>
      <Page hash={hash} />
    </main>
  );
}
