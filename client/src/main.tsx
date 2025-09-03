import React from "react";
import { createRoot } from "react-dom/client";
import ModernLogin from "./ModernLogin";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(<React.StrictMode><ModernLogin /></React.StrictMode>);