import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/components/Toast";
import "@/index.css";
import { installerDefilementTableaux } from "@/lib/defilementTableaux";   // règle du 18/11/2026 : tableaux de plus de 30 lignes

installerDefilementTableaux();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
