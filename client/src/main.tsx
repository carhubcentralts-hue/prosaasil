import React from "react";
import { createRoot } from "react-dom/client";
import EliteLoginApp from "./EliteLoginApp";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(<React.StrictMode><EliteLoginApp /></React.StrictMode>);