import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Forgot from "./pages/Forgot";
import Reset from "./pages/Reset";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace/>} />
        <Route path="/login" element={<Login/>} />
        <Route path="/forgot" element={<Forgot/>} />
        <Route path="/reset" element={<Reset/>} />
        <Route path="*" element={<Navigate to="/login" replace/>} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);