import React from "react";
import { createRoot } from "react-dom/client";
import ProfessionalLoginApp from "./ProfessionalLoginApp";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(<React.StrictMode><ProfessionalLoginApp /></React.StrictMode>);