import { BrowserRouter, Link, Route, Routes } from "react-router";
import { ClaimPage } from "./pages/ClaimPage";
import { InstructionsPage } from "./pages/InstructionsPage";
import { QueuePage } from "./pages/QueuePage";

export function App() {
  return (
    <BrowserRouter>
      <nav className="top-nav">
        <Link to="/">Queue</Link>
        <Link to="/instructions">Instructions</Link>
      </nav>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimPage />} />
        <Route path="/instructions" element={<InstructionsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
