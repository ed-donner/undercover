import { BrowserRouter, Route, Routes } from "react-router";
import { ClaimPage } from "./pages/ClaimPage";
import { QueuePage } from "./pages/QueuePage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimPage />} />
      </Routes>
    </BrowserRouter>
  );
}
