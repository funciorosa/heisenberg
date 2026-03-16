import { useState, useEffect, useRef, useCallback } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// GLOBAL CSS
// ─────────────────────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

.ws-root {
  position: fixed; inset: 0;
  background: #000;
  color: #00ff41;
  font-family: 'Share Tech Mono', monospace;
  font-size: 13px;
  overflow: hidden;
  z-index: 9999;
}
.ws-root::before {
  content: '';
  position: fixed; inset: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,255,65,0.015) 2px, rgba(0,255,65,0.015) 4px
  );
  pointer-events: none;
  z-index: 1000;
}

/* Fade wrapper */
.ws-fade {
  position: absolute; inset: 0;
  transition: opacity 0.3s ease;
}
.ws-fade.out { opacity: 0; }
.ws-fade.in  { opacity: 1; }

/* Screen container */
.ws-screen {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  padding: 40px 60px;
  box-sizing: border-box;
  overflow-y: auto;
}
.ws-screen::-webkit-scrollbar { width: 2px; }
.ws-screen::-webkit-scrollbar-thumb { background: #003b00; }

/* Progress bar */
.ws-progress {
  display: flex; gap: 24px;
  font-size: 10px; letter-spacing: 0.15em;
  color: #008f11;
  margin-bottom: 36px;
  flex-shrink: 0;
}
.ws-progress .step { cursor: default; }
.ws-progress .step.active { color: #00ff41; }

/* Title */
.ws-title {
  font-size: 18px;
  color: #00ff41;
  letter-spacing: 0.2em;
  margin-bottom: 32px;
  flex-shrink: 0;
  position: relative;
  display: inline-block;
}
.ws-title::after {
  content: attr(data-text);
  position: absolute; left: 2px; top: 0;
  color: rgba(0,255,65,0.3);
  clip-path: polygon(0 30%,100% 30%,100% 50%,0 50%);
  animation: glitch 4s infinite;
}
@keyframes glitch {
  0%,88%,100% { transform: translateX(0); }
  89% { transform: translateX(-3px); }
  91% { transform: translateX(3px); }
  93% { transform: translateX(-1px); }
}

/* Typewriter lines */
.ws-lines { flex: 1; font-size: 12px; line-height: 2; color: #00cc33; }
.ws-line { display: block; min-height: 1.2em; white-space: pre-wrap; }
.ws-cursor {
  display: inline-block; width: 8px; height: 13px;
  background: #00ff41; vertical-align: middle;
  animation: blink 0.8s step-start infinite;
}
@keyframes blink { 0%,100% {opacity:1} 50% {opacity:0} }

/* Checklist */
.ws-check-item {
  display: flex; align-items: baseline; gap: 10px;
  margin-bottom: 16px; font-size: 12px; color: #00cc33;
  opacity: 0; transition: opacity 0.3s;
}
.ws-check-item.visible { opacity: 1; }
.ws-check-box {
  font-size: 14px; flex-shrink: 0;
  transition: color 0.3s;
}
.ws-check-box.done { color: #00ff41; }
.ws-check-link { color: #008f11; text-decoration: none; }
.ws-check-link:hover { color: #00ff41; text-decoration: underline; }

/* Risk items */
.ws-risk-item {
  display: flex; align-items: flex-start; gap: 10px;
  margin-bottom: 14px; font-size: 12px;
  opacity: 0; transition: opacity 0.3s;
}
.ws-risk-item.visible { opacity: 1; }
.ws-risk-red  { color: #ff3131; }
.ws-risk-amber{ color: #ffe600; }
.ws-risk-green{ color: #00ff41; }
.ws-risk-sub  {
  padding-left: 16px; margin-top: 4px;
  font-size: 11px; color: #00cc33; line-height: 1.9;
}

/* Checkbox */
.ws-agree {
  display: flex; align-items: flex-start; gap: 10px;
  margin: 24px 0; font-size: 11px; color: #00cc33;
  cursor: pointer; user-select: none;
}
.ws-agree input[type=checkbox] {
  width: 14px; height: 14px; margin-top: 1px; flex-shrink: 0;
  accent-color: #00ff41; cursor: pointer;
}

/* Buttons */
.ws-btn {
  padding: 10px 24px;
  background: transparent;
  border: 1px solid #00ff41;
  color: #00ff41;
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.15em;
  cursor: pointer;
  transition: background 0.2s, opacity 0.3s;
  text-transform: uppercase;
}
.ws-btn:hover:not(:disabled) { background: rgba(0,255,65,0.1); }
.ws-btn:disabled {
  opacity: 0.3; cursor: not-allowed; border-color: #008f11; color: #008f11;
}
.ws-btn-white {
  padding: 10px 24px; background: transparent;
  border: 1px solid #fff; color: #fff;
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px; letter-spacing: 0.15em;
  cursor: pointer; transition: background 0.2s;
  text-transform: uppercase;
}
.ws-btn-white:hover { background: rgba(255,255,255,0.08); }
.ws-btn-back {
  background: transparent; border: none;
  color: #008f11; font-family: 'Share Tech Mono', monospace;
  font-size: 10px; letter-spacing: 0.1em; cursor: pointer;
  padding: 0; text-decoration: underline;
}
.ws-btn-back:hover { color: #00cc33; }

/* Fade-in helper */
.ws-fadein { animation: fadeIn 0.5s ease forwards; }
@keyframes fadeIn { from {opacity:0} to {opacity:1} }

/* Rabbit hole */
.ws-rabbit-screen {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 0;
}
.ws-rabbit-img {
  width: 180px;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  opacity: 0;
  transition: opacity 0.8s;
  animation: breathe 4s ease-in-out infinite, earTwitch 3s ease-in-out infinite;
}
.ws-rabbit-img.show { opacity: 1; }
@keyframes breathe {
  0%,100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
@keyframes earTwitch {
  0%,90%,100% { transform: translateY(0) scale(1); }
  92% { transform: translateY(-3px) scale(1); }
  94% { transform: translateY(0) scale(1); }
}
.ws-rabbit-line1 {
  margin-top: 28px; font-size: 14px; color: #fff;
  letter-spacing: 0.1em; min-height: 20px;
}
.ws-rabbit-line2 {
  margin-top: 10px; font-size: 14px; color: #00ff41;
  letter-spacing: 0.1em; min-height: 20px;
}
.ws-rabbit-btn-wrap {
  margin-top: 36px; opacity: 0; transition: opacity 0.6s;
}
.ws-rabbit-btn-wrap.show { opacity: 1; }
.ws-crt-flicker { animation: crtFlicker 3s ease-in-out infinite; }
@keyframes crtFlicker {
  0%,100% { opacity: 1; }
  50% { opacity: 0.85; }
}

/* Matrix canvas */
.ws-matrix-canvas {
  position: fixed; inset: 0; z-index: 500;
  pointer-events: none;
}
.ws-white-flash {
  position: fixed; inset: 0; z-index: 600;
  background: #fff; pointer-events: none;
  opacity: 0; transition: opacity 0.05s;
}
.ws-white-flash.on { opacity: 1; }

/* Screen 4 — Connect */
.ws-connect-section {
  margin-bottom: 28px; padding: 16px;
  border: 1px solid #003b00;
  background: rgba(0,255,65,0.02);
}
.ws-connect-label {
  font-size: 9px; letter-spacing: 0.2em; color: #008f11;
  text-transform: uppercase; margin-bottom: 10px;
}
.ws-address-row {
  font-size: 12px; color: #00ff41; margin-bottom: 6px;
}
.ws-balance-row {
  font-size: 11px; color: #00cc33;
}
.ws-input {
  background: #000; border: 1px solid #003b00;
  color: #00ff41; font-family: 'Share Tech Mono', monospace;
  font-size: 12px; padding: 8px 10px;
  width: 200px; outline: none;
  transition: border-color 0.2s;
}
.ws-input:focus { border-color: #00ff41; }
.ws-input-full { width: 100%; box-sizing: border-box; }
.ws-max-pos { font-size: 10px; color: #008f11; margin-top: 6px; }
.ws-mode-row { display: flex; gap: 12px; }
.ws-mode-btn {
  padding: 8px 20px; background: transparent;
  font-family: 'Share Tech Mono', monospace; font-size: 11px;
  letter-spacing: 0.1em; cursor: pointer;
  transition: all 0.2s; border: 1px solid #003b00; color: #008f11;
}
.ws-mode-btn.selected { border-color: #00ff41; color: #00ff41; }
.ws-mode-btn:hover:not(.selected) { border-color: #00cc33; color: #00cc33; }
.ws-api-toggle {
  background: none; border: none; color: #008f11;
  font-family: 'Share Tech Mono', monospace;
  font-size: 10px; cursor: pointer; padding: 0;
  letter-spacing: 0.1em; text-decoration: underline;
}
.ws-api-toggle:hover { color: #00cc33; }
.ws-api-note { font-size: 10px; color: #008f11; margin-top: 6px; }
.ws-btn-row {
  display: flex; align-items: center;
  justify-content: space-between; margin-top: 24px;
  flex-shrink: 0;
}

/* Warning tooltip */
.ws-live-warn {
  position: absolute; bottom: 36px; left: 0;
  background: #000; border: 1px solid #ffe600;
  color: #ffe600; font-size: 10px; padding: 6px 10px;
  white-space: nowrap; pointer-events: none;
  opacity: 0; transition: opacity 0.2s;
}
.ws-mode-btn:hover + .ws-live-warn { opacity: 1; }
`;

// ─────────────────────────────────────────────────────────────────────────────
// TYPEWRITER HOOK
// ─────────────────────────────────────────────────────────────────────────────
function useTypewriter(lines, speed = 18, startDelay = 0) {
  const [displayed, setDisplayed] = useState([]); // [{text, done}]
  const [activeLine, setActiveLine] = useState(-1);
  const [charIdx, setCharIdx] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setActiveLine(0), startDelay);
    return () => clearTimeout(t);
  }, [startDelay]);

  useEffect(() => {
    if (activeLine < 0 || activeLine >= lines.length) return;
    if (activeLine >= displayed.length) {
      setDisplayed(prev => [...prev, { text: "", done: false }]);
      setCharIdx(0);
      return;
    }
    const target = lines[activeLine];
    if (charIdx < target.length) {
      const t = setTimeout(() => {
        setDisplayed(prev => {
          const next = [...prev];
          next[activeLine] = { text: target.slice(0, charIdx + 1), done: false };
          return next;
        });
        setCharIdx(c => c + 1);
      }, speed);
      return () => clearTimeout(t);
    } else {
      setDisplayed(prev => {
        const next = [...prev];
        next[activeLine] = { text: target, done: true };
        return next;
      });
      if (activeLine + 1 < lines.length) {
        const t = setTimeout(() => {
          setActiveLine(a => a + 1);
        }, 120);
        return () => clearTimeout(t);
      } else {
        setDone(true);
      }
    }
  }, [activeLine, charIdx, lines, speed, displayed.length]);

  return { displayed, activeLine, done };
}

// ─────────────────────────────────────────────────────────────────────────────
// PROGRESS INDICATOR
// ─────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { n: "①", label: "WHAT IS IT" },
  { n: "②", label: "REQUIREMENTS" },
  { n: "③", label: "RISKS" },
  { n: "④", label: "CONNECT" },
];

function Progress({ active }) {
  return (
    <div className="ws-progress">
      {STEPS.map((s, i) => (
        <span key={i} className={`step${i === active ? " active" : ""}`}>
          {s.n} {s.label}
        </span>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 1 — WHAT IS HEISENBERG
// ─────────────────────────────────────────────────────────────────────────────
const S1_LINES = [
  "> HEISENBERG is an automated arbitrage bot for Polymarket's BTC prediction markets.",
  "> It scans markets every 5 seconds, looking for mispricings —",
  "  moments where the market's implied probability diverges from what the math says.",
  "> When it finds an edge, it places a limit order automatically.",
  "  When the market resolves, it collects the profit.",
  "> Small edges. Hundreds of times per hour. Compounding.",
];

function Screen1({ onNext }) {
  const { displayed, activeLine, done } = useTypewriter(S1_LINES, 18, 400);
  const [btnVisible, setBtnVisible] = useState(false);

  useEffect(() => {
    if (done) {
      const t = setTimeout(() => setBtnVisible(true), 600);
      return () => clearTimeout(t);
    }
  }, [done]);

  return (
    <div className="ws-screen">
      <Progress active={0} />
      <div className="ws-title" data-text="BRIEFING // WHAT IS HEISENBERG">
        BRIEFING // WHAT IS HEISENBERG
      </div>
      <div className="ws-lines">
        {displayed.map((d, i) => (
          <span key={i} className="ws-line">
            {d.text}
            {activeLine === i && !d.done && <span className="ws-cursor" />}
          </span>
        ))}
      </div>
      <div className="ws-btn-row">
        <span />
        {btnVisible && (
          <button className="ws-btn ws-fadein" onClick={onNext}>
            UNDERSTOOD → WHAT DO I NEED?
          </button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 2 — REQUIREMENTS
// ─────────────────────────────────────────────────────────────────────────────
const REQS = [
  { text: "MetaMask wallet installed", link: "https://metamask.io", linkLabel: "metamask.io" },
  {
    text: "MetaMask connected to Polygon Mainnet (chainId 137)",
    subs: [
      "→ Both USDC and POL (MATIC) must be on Polygon network",
      "→ Not Ethereum, not BSC, not Arbitrum — Polygon only",
      "→ RPC: https://polygon-rpc.com",
    ],
  },
  { text: "USDC in wallet — minimum $50 recommended (NOT ETH)", link: null },
  {
    text: "A small amount of POL (MATIC) for gas fees",
    subs: [
      "→ ~$1 worth covers hundreds of transactions",
      "→ ~$0.001 per trade",
      "→ Must be on Polygon network, not Ethereum",
    ],
  },
  { text: "Polymarket API key", link: "https://polymarket.com", linkLabel: "polymarket.com → Settings → API Keys → Create Key" },
];

function Screen2({ onNext, onBack }) {
  const [visible, setVisible] = useState([]);
  const [checked, setChecked] = useState([]);

  useEffect(() => {
    REQS.forEach((_, i) => {
      const t = setTimeout(() => {
        setVisible(v => [...v, i]);
        setTimeout(() => setChecked(c => [...c, i]), 600 + i * 80);
      }, 300 + i * 400);
      return () => clearTimeout(t);
    });
  }, []);

  const allChecked = checked.length === REQS.length;

  return (
    <div className="ws-screen">
      <Progress active={1} />
      <div className="ws-title" data-text="BRIEFING // WHAT YOU NEED">
        BRIEFING // WHAT YOU NEED
      </div>
      <div style={{ flex: 1 }}>
        {REQS.map((r, i) => (
          <div key={i} className={`ws-check-item${visible.includes(i) ? " visible" : ""}`}>
            <span className={`ws-check-box${checked.includes(i) ? " done" : ""}`}>
              {checked.includes(i) ? "✓" : "□"}
            </span>
            <span>
              {r.text}
              {r.link && (
                <> → <a className="ws-check-link" href={r.link} target="_blank" rel="noreferrer">
                  {r.linkLabel}
                </a></>
              )}
              {r.subs && (
                <div style={{ paddingLeft: 14, marginTop: 4, fontSize: 11, color: "#008f11", lineHeight: 1.9 }}>
                  {r.subs.map((s, j) => <div key={j}>{s}</div>)}
                </div>
              )}
            </span>
          </div>
        ))}
      </div>
      <div className="ws-btn-row">
        <button className="ws-btn-back" onClick={onBack}>← BACK</button>
        <button className="ws-btn" onClick={onNext} disabled={!allChecked}>
          I HAVE EVERYTHING → UNDERSTAND THE RISKS
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 3 — RISKS
// ─────────────────────────────────────────────────────────────────────────────
const RISKS = [
  { color: "red",   text: "● REAL MONEY AT RISK — You can lose your entire deposit." },
  { color: "amber", text: "● THE EDGE CAN DISAPPEAR — Past signals don't guarantee future profits." },
  { color: "amber", text: "● TECHNICAL RISK — Bugs and outages can cause unexpected behavior." },
  {
    color: "green",
    text: "● BUILT-IN PROTECTIONS:",
    subs: [
      "✓ Max 2% of capital per trade (fractional Kelly)",
      "✓ Paper trading mode by default",
      "✓ Auto-cancel orders older than 4 minutes",
      "✓ Min net edge: 0.5% after fees",
      "✓ Ctrl+C cancels all open orders cleanly",
    ],
  },
];

function Screen3({ onNext, onBack }) {
  const [visible, setVisible] = useState([]);
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    RISKS.forEach((_, i) => {
      const t = setTimeout(() => setVisible(v => [...v, i]), 400 + i * 500);
      return () => clearTimeout(t);
    });
  }, []);

  const colorClass = { red: "ws-risk-red", amber: "ws-risk-amber", green: "ws-risk-green" };

  return (
    <div className="ws-screen">
      <Progress active={2} />
      <div className="ws-title" data-text="BRIEFING // RISKS & RULES">
        BRIEFING // RISKS & RULES
      </div>
      <div style={{ flex: 1 }}>
        {RISKS.map((r, i) => (
          <div key={i} className={`ws-risk-item${visible.includes(i) ? " visible" : ""}`}>
            <div>
              <span className={colorClass[r.color]}>{r.text}</span>
              {r.subs && (
                <div className="ws-risk-sub">
                  {r.subs.map((s, j) => <div key={j}>{s}</div>)}
                </div>
              )}
            </div>
          </div>
        ))}
        {visible.length === RISKS.length && (
          <label className="ws-agree ws-fadein">
            <input
              type="checkbox"
              checked={agreed}
              onChange={e => setAgreed(e.target.checked)}
            />
            <span>
              I understand this is experimental software.
              I accept full responsibility for any losses.
            </span>
          </label>
        )}
      </div>
      <div className="ws-btn-row">
        <button className="ws-btn-back" onClick={onBack}>← BACK</button>
        <button className="ws-btn" onClick={onNext} disabled={!agreed}>
          ACCEPT &amp; CONTINUE →
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MATRIX RAIN (for rabbit hole transition)
// ─────────────────────────────────────────────────────────────────────────────
function MatrixRain({ active, onDone }) {
  const ref = useRef(null);
  const raf = useRef(null);

  useEffect(() => {
    if (!active) return;
    const c = ref.current;
    if (!c) return;
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    const ctx = c.getContext("2d");
    const cols = Math.floor(c.width / 14);
    const drops = Array.from({ length: cols }, () => Math.random() * -50);
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()ｦｧｨｩｪｫｬｭｮｯ";

    const draw = () => {
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.fillStyle = "#00ff41";
      ctx.font = "13px 'Share Tech Mono', monospace";
      drops.forEach((y, i) => {
        const ch = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillText(ch, i * 14, y * 14);
        if (y * 14 > c.height && Math.random() > 0.975) drops[i] = 0;
        drops[i] += 0.5;
      });
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);

    const t = setTimeout(() => {
      cancelAnimationFrame(raf.current);
      onDone();
    }, 1500);

    return () => {
      cancelAnimationFrame(raf.current);
      clearTimeout(t);
    };
  }, [active, onDone]);

  if (!active) return null;
  return <canvas ref={ref} className="ws-matrix-canvas" />;
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 3.5 — THE RABBIT HOLE
// ─────────────────────────────────────────────────────────────────────────────
function ScreenRabbit({ onNext }) {
  const [imgVisible, setImgVisible] = useState(false);
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [btnVisible, setBtnVisible] = useState(false);
  const [matrixActive, setMatrixActive] = useState(false);
  const [flash, setFlash] = useState(false);
  const [btnGone, setBtnGone] = useState(false);

  const LINE1 = "You took the red pill.";
  const LINE2 = "Welcome to the real world.";

  const typeIt = useCallback((str, setter, speed, cb) => {
    let i = 0;
    const go = () => {
      if (i <= str.length) {
        setter(str.slice(0, i));
        i++;
        setTimeout(go, speed);
      } else if (cb) cb();
    };
    go();
  }, []);

  useEffect(() => {
    const t1 = setTimeout(() => setImgVisible(true), 800);
    const t2 = setTimeout(() => typeIt(LINE1, setLine1, 18, () => {
      const t3 = setTimeout(() => typeIt(LINE2, setLine2, 18, () => {
        const t4 = setTimeout(() => setBtnVisible(true), 500);
        return () => clearTimeout(t4);
      }), 600);
      return () => clearTimeout(t3);
    }), 2200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [typeIt]);

  const handleClick = useCallback(() => {
    setBtnGone(true);
    setMatrixActive(true);
  }, []);

  const handleMatrixDone = useCallback(() => {
    setFlash(true);
    setTimeout(() => {
      setFlash(false);
      onNext();
    }, 300);
  }, [onNext]);

  return (
    <>
      <div className="ws-rabbit-screen">
        <img
          src="/rabbit.png"
          alt="white rabbit"
          className={`ws-rabbit-img${imgVisible ? " show" : ""}`}
        />
        <div className="ws-rabbit-line1">{line1}</div>
        <div className="ws-rabbit-line2">{line2}</div>
        <div className={`ws-rabbit-btn-wrap${btnVisible && !btnGone ? " show" : ""}`}>
          <button className="ws-btn-white ws-crt-flicker" onClick={handleClick}>
            ARE YOU READY TO ENTER THE RABBIT HOLE?
          </button>
        </div>
      </div>
      <MatrixRain active={matrixActive} onDone={handleMatrixDone} />
      <div className={`ws-white-flash${flash ? " on" : ""}`} />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SCREEN 4 — CONNECT WALLET
// ─────────────────────────────────────────────────────────────────────────────
const POLYGON_CHAIN_ID = "0x89"; // 137

async function getUSDCBalance(provider, address) {
  // Polygon has two USDC contracts:
  // - Native USDC (Circle, 2023+): 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
  // - Bridged USDC.e (legacy PoS):  0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
  const CONTRACTS = [
    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", // native USDC
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", // USDC.e (bridged)
  ];
  const data = "0x70a08231" + address.slice(2).padStart(64, "0");
  let total = 0;
  for (const contract of CONTRACTS) {
    try {
      const result = await provider.request({
        method: "eth_call",
        params: [{ to: contract, data }, "latest"],
      });
      if (result && result !== "0x") {
        total += parseInt(result, 16) / 1e6;
      }
    } catch {
      // ignore individual contract failures
    }
  }
  return total;
}

async function getMATICBalance(provider, address) {
  try {
    const result = await provider.request({
      method: "eth_getBalance",
      params: [address, "latest"],
    });
    const raw = parseInt(result, 16);
    return raw / 1e18;
  } catch {
    return null;
  }
}

function Screen4({ onNext, onBack }) {
  const [address, setAddress] = useState(null);
  const [chainId, setChainId] = useState(null);
  const [usdcBal, setUsdcBal] = useState(null);
  const [polBal, setPolBal] = useState(null);
  const [mmError, setMmError] = useState(null);
  const [capital, setCapital] = useState(100);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [showApi, setShowApi] = useState(false);
  const [mode, setMode] = useState("paper");
  const [showLiveWarn, setShowLiveWarn] = useState(false);
  const [switching, setSwitching] = useState(false);

  const isPolygon = chainId === POLYGON_CHAIN_ID || chainId === "0x89" || chainId === 137 || chainId === "137";

  const fetchBalances = async (addr) => {
    const [usdc, pol] = await Promise.all([
      getUSDCBalance(window.ethereum, addr),
      getMATICBalance(window.ethereum, addr),
    ]);
    setUsdcBal(usdc);
    setPolBal(pol);
    if (usdc !== null && usdc > 0) setCapital(Math.min(100, Math.floor(usdc)));
  };

  const switchToPolygon = async () => {
    setSwitching(true);
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: POLYGON_CHAIN_ID }],
      });
      const newChain = await window.ethereum.request({ method: "eth_chainId" });
      setChainId(newChain);
      if (address) await fetchBalances(address);
    } catch (swErr) {
      if (swErr.code === 4902) {
        try {
          await window.ethereum.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: POLYGON_CHAIN_ID,
              chainName: "Polygon Mainnet",
              nativeCurrency: { name: "POL", symbol: "POL", decimals: 18 },
              rpcUrls: ["https://polygon-rpc.com"],
              blockExplorerUrls: ["https://polygonscan.com"],
            }],
          });
          const newChain = await window.ethereum.request({ method: "eth_chainId" });
          setChainId(newChain);
          if (address) await fetchBalances(address);
        } catch (addErr) {
          setMmError(addErr.message || "Failed to add Polygon network.");
        }
      } else {
        setMmError(swErr.message || "Network switch failed.");
      }
    }
    setSwitching(false);
  };

  const connectMM = async () => {
    if (!window.ethereum) {
      setMmError("MetaMask not detected. Install at metamask.io");
      return;
    }
    try {
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const addr = accounts[0];
      const cid = await window.ethereum.request({ method: "eth_chainId" });
      setAddress(addr);
      setChainId(cid);
      const onPoly = cid === POLYGON_CHAIN_ID;
      if (onPoly) {
        await fetchBalances(addr);
      }
    } catch (e) {
      setMmError(e.message || "Connection failed.");
    }
  };

  const truncate = addr => addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : "";
  const maxPos = (capital * 0.02).toFixed(2);

  const canLaunch = address && isPolygon && capital >= 10 && (mode === "paper" || (apiKey && apiSecret));

  const launch = () => {
    if (!canLaunch) return;
    localStorage.setItem("hb_onboarded", JSON.stringify({
      address,
      startingCapital: capital,
      mode,
      apiKey,
      apiSecret,
      startTime: Date.now(),
    }));
    onNext({ address, startingCapital: capital, mode });
  };

  return (
    <div className="ws-screen">
      <Progress active={3} />
      <div className="ws-title" data-text="BRIEFING // CONNECT & CONFIGURE">
        BRIEFING // CONNECT &amp; CONFIGURE
      </div>

      {/* Step 1 — MetaMask */}
      <div className="ws-connect-section">
        <div className="ws-connect-label">Step 1 — Connect Wallet</div>
        {!address ? (
          <>
            <button className="ws-btn" onClick={connectMM}>CONNECT METAMASK</button>
            {mmError && (
              <div style={{ color: "#ff3131", fontSize: 11, marginTop: 8 }}>{mmError}</div>
            )}
          </>
        ) : (
          <>
            <div className="ws-address-row">✓ {truncate(address)}</div>
            {!isPolygon ? (
              <div style={{ marginTop: 8 }}>
                <div style={{ color: "#ffe600", fontSize: 11, marginBottom: 8 }}>
                  ⚠ Please switch MetaMask to Polygon Mainnet
                </div>
                <button className="ws-btn" onClick={switchToPolygon} disabled={switching}>
                  {switching ? "SWITCHING..." : "SWITCH TO POLYGON"}
                </button>
              </div>
            ) : (
              <>
                <div className="ws-balance-row" style={{ marginTop: 6 }}>
                  USDC: {usdcBal !== null ? `$${usdcBal.toFixed(2)}` : "—"}
                  &nbsp;&nbsp;|&nbsp;&nbsp;
                  POL (MATIC): {polBal !== null ? polBal.toFixed(4) : "—"}
                </div>
                <div style={{ fontSize: 10, color: "#004d00", marginTop: 6 }}>
                  Make sure both tokens are on Polygon Mainnet.
                  Tokens on other networks won't be detected.
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Step 2 — Capital */}
      {address && isPolygon && (
        <div className="ws-connect-section ws-fadein">
          <div className="ws-connect-label">Step 2 — Starting Capital (USDC)</div>
          <input
            className="ws-input"
            type="number"
            min={10}
            max={usdcBal !== null && usdcBal > 0 ? usdcBal : undefined}
            value={capital}
            onChange={e => setCapital(Number(e.target.value))}
          />
          {usdcBal !== null && usdcBal > 0 && (
            <div className="ws-max-pos">WALLET MAX: ${usdcBal.toFixed(2)} USDC</div>
          )}
          <div className="ws-max-pos">MAX POSITION PER TRADE: ${maxPos} (2% of capital)</div>
          {usdcBal !== null && usdcBal === 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ color: "#ffe600", fontSize: 11 }}>
                ⚠ No USDC detected on Polygon. Deposit USDC to your wallet before launching.
              </div>
              <a
                href="https://polygon.technology/usdc"
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: 10, color: "#008f11", textDecoration: "underline" }}
              >
                How to get USDC on Polygon →
              </a>
            </div>
          )}
        </div>
      )}

      {/* Step 3 — API Keys */}
      {address && isPolygon && (
        <div className="ws-connect-section ws-fadein">
          <div className="ws-connect-label">
            Step 3 — API Keys&nbsp;
            <button className="ws-api-toggle" onClick={() => setShowApi(s => !s)}>
              {showApi ? "▲ hide" : "▼ expand (optional for paper trading)"}
            </button>
          </div>
          {showApi && (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: "#008f11", marginBottom: 4 }}>POLYMARKET API KEY</div>
                <input
                  className="ws-input ws-input-full"
                  type="password"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="0x..."
                />
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#008f11", marginBottom: 4 }}>POLYMARKET API SECRET</div>
                <input
                  className="ws-input ws-input-full"
                  type="password"
                  value={apiSecret}
                  onChange={e => setApiSecret(e.target.value)}
                  placeholder="secret..."
                />
              </div>
              <div className="ws-api-note">Required only for LIVE trading.</div>
            </>
          )}
        </div>
      )}

      {/* Step 4 — Mode */}
      {address && isPolygon && (
        <div className="ws-connect-section ws-fadein">
          <div className="ws-connect-label">Step 4 — Trading Mode</div>
          <div className="ws-mode-row">
            <button
              className={`ws-mode-btn${mode === "paper" ? " selected" : ""}`}
              onClick={() => setMode("paper")}
            >
              PAPER TRADING
            </button>
            <div style={{ position: "relative" }}>
              <button
                className={`ws-mode-btn${mode === "live" ? " selected" : ""}`}
                onClick={() => setMode("live")}
                onMouseEnter={() => setShowLiveWarn(true)}
                onMouseLeave={() => setShowLiveWarn(false)}
              >
                LIVE TRADING
              </button>
              {showLiveWarn && (
                <div style={{
                  position: "absolute", bottom: "calc(100% + 8px)", left: 0,
                  background: "#000", border: "1px solid #ffe600",
                  color: "#ffe600", fontSize: 10, padding: "6px 10px",
                  whiteSpace: "nowrap",
                }}>
                  ⚠ Real orders. Real USDC.
                </div>
              )}
            </div>
          </div>
          {mode === "live" && !apiKey && (
            <div style={{ color: "#ffe600", fontSize: 10, marginTop: 8 }}>
              ⚠ API key required for live trading.
            </div>
          )}
        </div>
      )}

      <div className="ws-btn-row">
        <button className="ws-btn-back" onClick={onBack}>← BACK</button>
        {address && isPolygon && (
          <button className="ws-btn ws-fadein" onClick={launch} disabled={!canLaunch}>
            LAUNCH HEISENBERG
          </button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ROOT — WelcomeScreen
// ─────────────────────────────────────────────────────────────────────────────
export default function WelcomeScreen({ onComplete }) {
  // 0=s1, 1=s2, 2=s3, 3=rabbit, 4=s4
  const [screen, setScreen] = useState(0);
  const [fading, setFading] = useState(false);
  const [visible, setVisible] = useState(true);

  const goTo = useCallback((next) => {
    setFading(true);
    setVisible(false);
    setTimeout(() => {
      setScreen(next);
      setFading(false);
      setVisible(true);
    }, 300);
  }, []);

  const handleLaunch = useCallback((data) => {
    setFading(true);
    setVisible(false);
    setTimeout(() => onComplete(data), 300);
  }, [onComplete]);

  const screens = [
    <Screen1 key="s1" onNext={() => goTo(1)} />,
    <Screen2 key="s2" onNext={() => goTo(2)} onBack={() => goTo(0)} />,
    <Screen3 key="s3" onNext={() => goTo(3)} onBack={() => goTo(1)} />,
    <ScreenRabbit key="rabbit" onNext={() => goTo(4)} />,
    <Screen4 key="s4" onNext={handleLaunch} onBack={() => goTo(2)} />,
  ];

  return (
    <div className="ws-root">
      <style>{GLOBAL_CSS}</style>
      <div className={`ws-fade${visible ? " in" : " out"}`}>
        {screens[screen]}
      </div>
    </div>
  );
}
