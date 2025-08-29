import React from "react";
import { createRoot } from "react-dom/client";
import Login from "./pages/Login.jsx";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(<React.StrictMode><Login /></React.StrictMode>);