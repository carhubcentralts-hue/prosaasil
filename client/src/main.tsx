import React from "react";
import { createRoot } from "react-dom/client";
import Login from "./pages/Login.jsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Login />
  </React.StrictMode>
);