import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ReplayProvider } from "./state/ReplayContext";
import { DashboardPage } from "./pages/DashboardPage";
import "./styles/tokens.css";
import "./styles/dashboard.css";

const root = createRoot(document.getElementById("root")!);
root.render(
  <StrictMode>
    <ReplayProvider>
      <DashboardPage />
    </ReplayProvider>
  </StrictMode>
);
