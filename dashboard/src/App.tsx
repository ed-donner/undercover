import { NavLink, Route, BrowserRouter, Routes } from "react-router-dom";
import "./brand.css";
import { ClaimDetail } from "./pages/ClaimDetail";
import { Instructions } from "./pages/Instructions";
import { Queue } from "./pages/Queue";

export function App() {
  return (
    <BrowserRouter>
      <nav>
        <strong>UnderCover</strong>
        <NavLink to="/">Queue</NavLink>
        <NavLink to="/instructions">Instructions</NavLink>
      </nav>
      <main>
        <Routes>
          <Route element={<Queue />} path="/" />
          <Route element={<ClaimDetail />} path="/claims/:claimId" />
          <Route element={<Instructions />} path="/instructions" />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
