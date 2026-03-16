import { useState } from "react";
import WelcomeScreen from "./WelcomeScreen";
import Heisenberg from "./Heisenberg";

const STORAGE_KEY = "hb_onboarded";

export default function App() {
  const [onboarded, setOnboarded] = useState(() => {
    try {
      return !!localStorage.getItem(STORAGE_KEY);
    } catch {
      return false;
    }
  });

  const [config, setConfig] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  function handleComplete(data) {
    setConfig(data);
    setOnboarded(true);
  }

  function handleReviewBriefing() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
    window.location.reload();
  }

  if (!onboarded) {
    return <WelcomeScreen onComplete={handleComplete} />;
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <Heisenberg
        address={config?.address}
        startingCapital={config?.startingCapital}
        mode={config?.mode}
      />
      <div
        style={{
          position: "fixed",
          bottom: "12px",
          right: "16px",
          zIndex: 9999,
        }}
      >
        <button
          onClick={handleReviewBriefing}
          style={{
            background: "transparent",
            border: "none",
            color: "rgba(0,255,65,0.25)",
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "11px",
            cursor: "pointer",
            letterSpacing: "0.1em",
            padding: "4px 8px",
            transition: "color 0.2s",
          }}
          onMouseEnter={(e) => (e.target.style.color = "rgba(0,255,65,0.7)")}
          onMouseLeave={(e) => (e.target.style.color = "rgba(0,255,65,0.25)")}
        >
          [ REVIEW BRIEFING ]
        </button>
      </div>
    </div>
  );
}
