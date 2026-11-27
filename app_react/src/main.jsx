import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./estilo/tema.css";
import "./estilo/base.css";

createRoot(document.getElementById("raiz")).render(<App />);
