import { Claim } from "./Claim";
import { useHash } from "./hooks";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

const CLAIM_ROUTE = /^#\/claims\/([\w-]+)$/;

export function App() {
  const hash = useHash();
  const claimId = CLAIM_ROUTE.exec(hash)?.[1];
  let page = <Queue />;
  if (claimId) page = <Claim key={claimId} claimId={claimId} />;
  else if (hash === "#/instructions") page = <Instructions />;

  return (
    <div className="shell">
      <header>
        <a href="#/" className="brand">
          UnderCover
        </a>
        <span className="tagline">Travel insurance claims</span>
        <nav>
          <a href="#/">Queue</a>
          <a href="#/instructions">Instructions</a>
        </nav>
      </header>
      <main>{page}</main>
    </div>
  );
}
