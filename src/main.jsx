import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Heisenberg from "./Heisenberg";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Heisenberg />
  </StrictMode>
);
