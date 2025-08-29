import React from "react";
import ReactDOM from "react-dom/client";
import { Route, Router } from "wouter";
import Login from "./pages/Login";
import Forgot from "./pages/Forgot";
import Reset from "./pages/Reset";
import "./index.css";

function App() {
  return (
    <Router>
      <Route path="/" component={Login} />
      <Route path="/login" component={Login} />
      <Route path="/forgot" component={Forgot} />
      <Route path="/reset" component={Reset} />
    </Router>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);