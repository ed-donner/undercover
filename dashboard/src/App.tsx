import { useEffect, useState } from "react";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";
import "./styles.css";

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);
  return hash;
}

export function App() {
  const [status, setStatus] = useState("checking");
  const hash = useHash();

  useEffect(() => {
    void fetch("/api/health")
      .then((response) => (response.ok ? "up" : "down"))
      .catch(() => "down")
      .then(setStatus);
  }, []);

  const claimId = /^#\/claims\/(.+)$/.exec(hash)?.[1];
  let page = <QueuePage />;
  if (claimId) page = <ClaimPage claimId={claimId} />;
  else if (hash === "#/instructions") page = <InstructionsPage />;

  return (
    <>
      <header>
        <h1>UnderCover</h1>
        <nav>
          <a href="#/">Queue</a>
          <a href="#/instructions">Instructions</a>
        </nav>
        <span className="muted">Backend: {status}</span>
      </header>
      <main>{page}</main>
    </>
  );
}
