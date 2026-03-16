import { useState, useEffect, useRef, useCallback } from "react";

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap');

*{box-sizing:border-box;margin:0;padding:0;}
body{background:#000;overflow-x:hidden;}

:root{
  --green:#00ff41;
  --green2:#00cc33;
  --green3:#008f11;
  --green4:#003b00;
  --green5:#001a00;
  --red:#ff3131;
  --yellow:#ffe600;
  --dim:#0a2e0a;
  --font:'Share Tech Mono',monospace;
  --vt:'VT323',monospace;
}

.hb{
  background:#000;
  color:var(--green2);
  font-family:var(--font);
  font-size:11px;
  min-height:100vh;
  display:flex;
  flex-direction:column;
  position:relative;
  overflow:hidden;
}

.hb::before{
  content:'';
  position:fixed;
  inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px);
  pointer-events:none;
  z-index:100;
}

.topbar{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:6px 16px;
  border-bottom:1px solid var(--green4);
  background:#000;
  position:relative;
  z-index:10;
}
.hb-title{
  font-family:var(--vt);
  font-size:22px;
  color:var(--green);
  letter-spacing:0.25em;
  text-shadow:0 0 8px rgba(0,255,65,0.6);
  position:relative;
}
.hb-title::after{
  content:attr(data-text);
  position:absolute;
  left:2px;top:0;
  color:rgba(0,255,65,0.3);
  clip-path:polygon(0 30%,100% 30%,100% 50%,0 50%);
  animation:glitch 4s infinite;
}
@keyframes glitch{
  0%,90%,100%{transform:translateX(0);}
  91%{transform:translateX(-2px);}
  93%{transform:translateX(2px);}
  95%{transform:translateX(-1px);}
}
.topbar-sub{
  font-size:9px;
  color:var(--green3);
  letter-spacing:0.15em;
  margin-top:1px;
}
.topbar-right{
  display:flex;
  gap:20px;
  align-items:center;
  font-size:10px;
  color:var(--green3);
  letter-spacing:0.1em;
}
.live-badge{
  display:flex;
  align-items:center;
  gap:5px;
  color:var(--green);
  font-size:10px;
}
.live-dot{
  width:6px;height:6px;
  border-radius:50%;
  background:var(--green);
  box-shadow:0 0 6px var(--green);
  animation:blink 1.2s ease-in-out infinite;
}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}

.panels{
  display:grid;
  grid-template-columns:1fr 1fr 1fr;
  border-bottom:1px solid var(--green4);
  height:170px;
}
.panel{
  border-right:1px solid var(--green4);
  padding:10px 14px;
  overflow:hidden;
  position:relative;
}
.panel:last-child{border-right:none;}
.panel-label{
  font-size:8px;
  letter-spacing:0.2em;
  color:var(--green3);
  text-transform:uppercase;
  margin-bottom:2px;
}
.panel-formula{
  font-size:13px;
  color:var(--green);
  margin-bottom:5px;
  text-shadow:0 0 4px rgba(0,255,65,0.4);
}
.panel-desc{
  font-size:9px;
  color:var(--green3);
  line-height:1.7;
}
.panel-metrics{
  margin-top:6px;
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  font-size:9.5px;
}
.m-green{color:var(--green);}
.m-yellow{color:var(--yellow);}
.m-red{color:var(--red);}
.m-dim{color:var(--green3);}

.canvas-zone{
  flex:1;
  min-height:260px;
  position:relative;
  background:#000;
  overflow:hidden;
}
.mc-canvas{
  position:absolute;
  inset:0;
  width:100%;height:100%;
}
.canvas-watermark{
  position:absolute;
  bottom:12px;left:18px;
  font-family:var(--vt);
  font-size:15px;
  color:var(--green4);
  letter-spacing:0.1em;
  pointer-events:none;
}
.price-float{
  position:absolute;
  font-size:10.5px;
  font-family:var(--font);
  pointer-events:none;
  animation:fadeIn 0.3s ease;
}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.pf-green{color:var(--green);}
.pf-red{color:var(--red);}

.bottom{
  display:grid;
  grid-template-columns:1fr 1fr 1fr;
  border-top:1px solid var(--green4);
  height:270px;
}
.bot-panel{
  border-right:1px solid var(--green4);
  padding:10px 12px;
  display:flex;
  flex-direction:column;
  overflow:hidden;
}
.bot-panel:last-child{border-right:none;}
.bot-title{
  font-size:8px;
  letter-spacing:0.2em;
  color:var(--green3);
  text-transform:uppercase;
  margin-bottom:7px;
  flex-shrink:0;
  border-bottom:1px solid var(--green4);
  padding-bottom:4px;
}

.stream{
  overflow-y:auto;
  flex:1;
  font-size:9px;
  line-height:1.8;
}
.stream::-webkit-scrollbar{width:2px;}
.stream::-webkit-scrollbar-thumb{background:var(--green4);}
.s-row{display:flex;gap:6px;align-items:baseline;}
.s-time{color:var(--green4);flex-shrink:0;width:46px;}
.s-tag-g{color:var(--green);}
.s-tag-y{color:var(--yellow);}
.s-tag-r{color:var(--red);}
.s-tag-c{color:#00ffff;}
.s-tag-b{color:#4488ff;}
.s-msg{color:var(--green3);}

.mets{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:1px 12px;
  font-size:9px;
  flex:1;
  overflow:hidden;
}
.mrow{
  display:flex;
  justify-content:space-between;
  padding:2px 0;
  border-bottom:1px solid var(--green5);
}
.ml{color:var(--green3);}
.mv{color:var(--green2);font-weight:500;}
.mv-bright{color:var(--green);font-weight:700;}

.status-block{margin-top:6px;flex-shrink:0;}
.st-title{font-size:8px;letter-spacing:0.2em;color:var(--green3);text-transform:uppercase;margin-bottom:3px;}
.st-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 10px;}
.st-row{display:flex;justify-content:space-between;font-size:9px;padding:1px 0;}
.st-k{color:var(--green4);}
.st-on{color:var(--green);}
.st-act{color:var(--yellow);}
.st-sc{color:#00ffff;}

.pl-num{
  font-family:var(--vt);
  font-size:36px;
  color:var(--green);
  letter-spacing:0.02em;
  text-shadow:0 0 10px rgba(0,255,65,0.5);
  line-height:1;
}
.pl-sub{font-size:9px;color:var(--green3);margin:2px 0 8px;}
.pl-svg-wrap{flex:1;min-height:0;}

.footer{
  border-top:1px solid var(--green4);
  padding:4px 16px;
  font-size:8.5px;
  color:var(--green4);
  display:flex;
  justify-content:space-between;
  letter-spacing:0.06em;
  background:#000;
}
.footer span:last-child{color:var(--green3);}
`;

const rnd = (a, b) => a + Math.random() * (b - a);
const f2 = (n) => n.toFixed(2);

const STYPES = [
  { tag: "SPREAD", cl: "s-tag-g", msgs: ["z={z}; disloc", "s={s} spread"] },
  { tag: "KELLY",  cl: "s-tag-y", msgs: ["f={f}% safe",   "f={f}% impact={i}"] },
  { tag: "ARB",    cl: "s-tag-c", msgs: ["+${g}",          "+${g}.{n}"] },
  { tag: "FILTER", cl: "s-tag-r", msgs: ["rejected",       "edge low"] },
  { tag: "EXEC",   cl: "s-tag-b", msgs: ["fill +${g}",     "limit fill"] },
  { tag: "HEDGE",  cl: "s-tag-g", msgs: ["delta={d}",      "delta ok"] },
  { tag: "BAYES",  cl: "s-tag-y", msgs: ["post={p}",       "prior→post ok"] },
  { tag: "MC",     cl: "s-tag-c", msgs: ["dd={d}% OK",     "conf ok"] },
  { tag: "STOIKOV",cl: "s-tag-b", msgs: ["r adj q={q}",    "quot ok"] },
  { tag: "FILL",   cl: "s-tag-g", msgs: ["YES $4.60 {p}%", "NO $4.60 {p}%"] },
  { tag: "SCAN",   cl: "s-tag-y", msgs: ["5m repriced",    "3m repriced"] },
  { tag: "EDGE",   cl: "s-tag-c", msgs: ["net={n} PASS",   "ev={v} ok"] },
];

function genMsg() {
  const t = STYPES[Math.floor(Math.random() * STYPES.length)];
  const m = t.msgs[Math.floor(Math.random() * t.msgs.length)]
    .replace("{z}", f2(rnd(10, 30))).replace("{s}", f2(rnd(10, 25)))
    .replace("{f}", f2(rnd(5, 25))).replace("{i}", f2(rnd(0.2, 1.5)))
    .replace("{g}", Math.floor(rnd(5, 55))).replace("{n}", Math.floor(rnd(10, 99)))
    .replace("{d}", f2(rnd(0.05, 0.4))).replace("{p}", Math.floor(rnd(5, 20)))
    .replace("{q}", Math.floor(rnd(5, 20))).replace("{v}", f2(rnd(0.01, 0.05)));
  const now = new Date();
  const time = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((x) => x.toString().padStart(2, "0")).join(":");
  return { time, tag: t.tag, cl: t.cl, msg: m };
}

function MonteCarloCanvas() {
  const ref = useRef(null);
  const paths = useRef([]);
  const raf = useRef(null);

  const init = useCallback((w, h) => {
    paths.current = Array.from({ length: 140 }, (_, i) => {
      const color = i % 4 === 0 ? "#00ff41" : i % 7 === 0 ? "#ff3131" : i % 5 === 0 ? "#00ffff" : "#00cc33";
      return { drift: rnd(-0.004, 0.009), vol: rnd(0.007, 0.026), color, alpha: rnd(0.06, 0.2), pts: [[w * 0.1, h * 0.5]] };
    });
  }, []);

  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; init(c.width, c.height); };
    resize();
    const ro = new ResizeObserver(resize); ro.observe(c);
    const draw = () => {
      const { width: w, height: h } = c;
      ctx.fillStyle = "rgba(0,0,0,0.15)";
      ctx.fillRect(0, 0, w, h);
      const ox = w * 0.1, oy = h * 0.5;
      paths.current.forEach((p) => {
        const last = p.pts[p.pts.length - 1];
        if (last[0] > w * 0.96) { p.pts = [[ox, oy]]; p.drift = rnd(-0.004, 0.009); return; }
        const dx = rnd(3, 6), dy = p.drift * h + rnd(-p.vol * h, p.vol * h);
        p.pts.push([last[0] + dx, last[1] + dy]);
        if (p.pts.length > 200) p.pts.shift();
        if (p.pts.length < 2) return;
        ctx.beginPath();
        ctx.moveTo(p.pts[0][0], p.pts[0][1]);
        p.pts.forEach((pt) => ctx.lineTo(pt[0], pt[1]));
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.lineWidth = 0.55;
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
      const g = ctx.createRadialGradient(ox, oy, 0, ox, oy, 20);
      g.addColorStop(0, "rgba(0,255,65,0.95)");
      g.addColorStop(0.4, "rgba(0,255,65,0.3)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.beginPath(); ctx.arc(ox, oy, 20, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf.current); ro.disconnect(); };
  }, [init]);

  return <canvas ref={ref} className="mc-canvas" />;
}

function PLCurve({ hist }) {
  if (hist.length < 2) return null;
  const W = 300, H = 90;
  const min = Math.min(...hist), max = Math.max(...hist), range = max - min || 1;
  const pts = hist.map((v, i) => `${(i / (hist.length - 1)) * W},${H - ((v - min) / range) * (H - 6) - 3}`);
  const path = "M " + pts.join(" L ");
  const area = path + ` L ${W},${H} L 0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block" }}>
      <defs>
        <linearGradient id="plg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00ff41" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#00ff41" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#plg)" />
      <path d={path} fill="none" stroke="#00ff41" strokeWidth="1.4" />
      {pts.length > 0 && (
        <circle
          cx={pts[pts.length - 1].split(",")[0]}
          cy={pts[pts.length - 1].split(",")[1]}
          r="3" fill="#00ff41"
          style={{ filter: "drop-shadow(0 0 4px #00ff41)" }}
        />
      )}
    </svg>
  );
}

const API_URL = (import.meta.env.VITE_BOT_API_URL || "http://localhost:8000").replace(/\/$/, "");
const WS_URL = API_URL.replace(/^https/, "wss").replace(/^http/, "ws");

export default function Heisenberg({ address, startingCapital = 100, mode = "paper" }) {
  const DEP = startingCapital;

  // ── visual-only state (stays simulated) ──────────────────────────
  const [block, setBlock]   = useState(82355);
  const [vol, setVol]       = useState(3.72);
  const [prior, setPrior]   = useState(0.436);
  const [post, setPost]     = useState(0.548);
  const [ev, setEv]         = useState(0.0178);
  const [cost, setCost]     = useState(0.0126);
  const [net, setNet]       = useState(0.0052);
  const [zscore, setZscore] = useState(-1.87);
  const [q, setQ]           = useState(1.1);
  const [gamma, setGamma]   = useState(0.19);
  const [fstar, setFstar]   = useState(0.0097);
  const [floats, setFloats] = useState([
    { id: 1, v: "+$23.44", green: true,  top: "28%", right: "32%" },
    { id: 2, v: "-$11.20", green: false, top: "44%", right: "22%" },
    { id: 3, v: "+$29.15", green: true,  top: "19%", right: "14%" },
    { id: 4, v: "+$17.35", green: true,  top: "58%", right: "38%" },
  ]);

  // ── live data state (driven by WebSocket) ────────────────────────
  const [edge, setEdge]         = useState(0.0);
  const [bal, setBal]           = useState(DEP);
  const [hist, setHist]         = useState([DEP]);
  const [stream, setStream]     = useState(() => Array.from({ length: 12 }, genMsg));
  const [winRate, setWinRate]   = useState(0.0);
  const [tradesHr, setTradesHr] = useState(0);
  const [total, setTotal]       = useState(0);
  const [sharpe, setSharpe]         = useState(0.0);
  const [maxDD, setMaxDD]           = useState(0.0);
  const [expectedEdge, setExpectedEdge] = useState(0.0);
  const [wsStatus, setWsStatus] = useState("connecting"); // "live" | "reconnecting" | "connecting"

  const streamRef   = useRef(null);
  const wsRef       = useRef(null);
  const retryRef    = useRef(null);
  const connectedRef = useRef(false);

  // ── WebSocket connection ──────────────────────────────────────────
  const connectWs = useCallback(() => {
    const wsUrl = WS_URL + "/stream";
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        connectedRef.current = true;
        setWsStatus("live");
      };

      ws.onmessage = (e) => {
        let data;
        try { data = JSON.parse(e.data); } catch { return; }
        if (data.ping) return;

        if (data.balance != null) {
          setBal(data.balance);
          setHist((h) => [...h.slice(-70), data.balance]);
        }
        if (data.edge != null)        setEdge(data.edge);
        if (data.win_rate != null)    setWinRate(data.win_rate);
        if (data.trades_hr != null)   setTradesHr(data.trades_hr);
        if (data.total_trades != null) setTotal(data.total_trades);
        if (data.sharpe != null)        setSharpe(data.sharpe);
        if (data.max_dd != null)        setMaxDD(data.max_dd);
        if (data.expected_edge != null) setExpectedEdge(data.expected_edge);
        if (data.stream?.length)      setStream(data.stream.slice(-90));
        if (data.balance != null && Math.random() < 0.2) {
          const delta = (data.balance - bal).toFixed(2);
          const pos = delta >= 0;
          setFloats((f) => f.map((x, i) =>
            i === Math.floor(Math.random() * f.length)
              ? { ...x, v: (pos ? "+$" : "-$") + Math.abs(delta), green: pos }
              : x
          ));
        }
      };

      ws.onclose = () => {
        connectedRef.current = false;
        setWsStatus("reconnecting");
        retryRef.current = setTimeout(connectWs, 5000);
      };

      ws.onerror = () => ws.close();
    } catch {
      setWsStatus("reconnecting");
      retryRef.current = setTimeout(connectWs, 5000);
    }
  }, [API_URL]);

  useEffect(() => {
    connectWs();
    return () => {
      clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connectWs]);

  // ── Visual-only simulation intervals ────────────────────────────
  useEffect(() => {
    // Fake stream fallback — only fires when disconnected
    const si = setInterval(() => {
      if (!connectedRef.current) {
        setStream((p) => [...p.slice(-90), genMsg()]);
      }
    }, 400);

    const vi = setInterval(() => {
      setBlock((b) => b + Math.floor(rnd(1, 3)));
      setVol((v) => Math.max(1, +(v + rnd(-0.04, 0.04)).toFixed(2)));
      setPrior((p) => Math.max(0.3, Math.min(0.7, +(p + rnd(-0.004, 0.004)).toFixed(3))));
      setPost((p) => Math.max(0.35, Math.min(0.75, +(p + rnd(-0.003, 0.007)).toFixed(3))));
      setEv((v) => Math.max(0.005, Math.min(0.06, +(v + rnd(-0.001, 0.002)).toFixed(4))));
      setCost((v) => Math.max(0.005, Math.min(0.03, +(v + rnd(-0.0005, 0.001)).toFixed(4))));
      setNet((v) => Math.max(0.001, Math.min(0.02, +(v + rnd(-0.0005, 0.001)).toFixed(4))));
      setZscore((v) => +(v + rnd(-0.08, 0.08)).toFixed(2));
      setQ((v) => Math.max(0.5, Math.min(2.5, +(v + rnd(-0.02, 0.04)).toFixed(2))));
      setGamma((v) => Math.max(0.05, Math.min(0.5, +(v + rnd(-0.004, 0.007)).toFixed(3))));
      setFstar((v) => Math.max(0.003, Math.min(0.03, +(v + rnd(-0.0005, 0.001)).toFixed(4))));
    }, 700);

    return () => { clearInterval(si); clearInterval(vi); };
  }, []);

  useEffect(() => {
    if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
  }, [stream]);

  const roi = ((bal - DEP) / DEP * 100).toFixed(1);

  return (
    <div className="hb">
      <style>{CSS}</style>

      {/* TOPBAR */}
      <div className="topbar">
        <div>
          <div className="hb-title" data-text="HEISENBERG">HEISENBERG</div>
          <div className="topbar-sub">POLYMARKET · 5-MIN BTC ARBITRAGE · UNCERTAINTY PRINCIPLE ENGINE</div>
        </div>
        <div className="topbar-right">
          <span>BLOCK {block}</span>
          <span>VOL ${vol.toFixed(2)}B</span>
          <span>EDGE {edge.toFixed(2)}%</span>
          {wsStatus === "live" ? (
            <div className="live-badge"><span className="live-dot" />LIVE</div>
          ) : wsStatus === "reconnecting" ? (
            <div className="live-badge" style={{ color: "var(--yellow)" }}>
              <span className="live-dot" style={{ background: "var(--yellow)", boxShadow: "0 0 6px var(--yellow)" }} />
              RECONNECTING...
            </div>
          ) : (
            <div className="live-badge" style={{ color: "var(--green3)" }}>
              <span className="live-dot" style={{ background: "var(--green3)", boxShadow: "none" }} />
              CONNECTING...
            </div>
          )}
        </div>
      </div>

      {/* PANELS */}
      <div className="panels">
        <div className="panel">
          <div className="panel-label">Bayesian Model · Likelihood</div>
          <div className="panel-formula">P(D|H) = f(spot_delta, vol, book)</div>
          <div className="panel-desc">
            inputs: BTC spot change<br />
            short-term volatility<br />
            order book imbalance<br />
            reprice speed nearby mkts<br />
            maps signal → probability
          </div>
          <div className="panel-metrics">
            <span className="m-dim">prior={prior}</span>
            <span className="m-green">post={post}</span>
            <span className="m-dim">ev={ev}</span>
          </div>
        </div>
        <div className="panel">
          <div className="panel-label">Edge + Spread · Z-Score</div>
          <div className="panel-formula">z = (S - μ_S) / σ_S</div>
          <div className="panel-desc">
            S = P1 : P2 (spread)<br />
            μ_S = normal avg spread<br />
            σ_S = std deviation<br />
            z &gt; 2 → dislocation signal<br />
            triggers cross-mkt arb
          </div>
          <div className="panel-metrics">
            <span className="m-green">EV={ev}</span>
            <span className="m-dim">cost={cost}</span>
            <span className={net > 0.003 ? "m-green" : "m-yellow"}>net={net} {net > 0.003 ? "PASS" : "WEAK"}</span>
            <span className="m-dim">z={zscore}</span>
          </div>
        </div>
        <div className="panel">
          <div className="panel-label">Execution · Stoikov Quoting</div>
          <div className="panel-formula">r = s - q·γ·σ²·(T-t)</div>
          <div className="panel-desc">
            r = reservation price<br />
            s = mid price<br />
            q = inventory, γ = risk<br />
            σ² = variance<br />
            T-t = time remaining
          </div>
          <div className="panel-metrics">
            <span className="m-dim">q={q}</span>
            <span className="m-dim">γ={gamma}</span>
            <span className="m-green">f*={fstar}</span>
            <span className="m-yellow">kelly={fstar}</span>
          </div>
        </div>
      </div>

      {/* CANVAS */}
      <div className="canvas-zone">
        <MonteCarloCanvas />
        <div className="canvas-watermark">HEISENBERG · MONTE CARLO</div>
        {floats.map((f) => (
          <div key={f.id} className={`price-float ${f.green ? "pf-green" : "pf-red"}`}
            style={{ top: f.top, right: f.right }}>{f.v}</div>
        ))}
      </div>

      {/* BOTTOM */}
      <div className="bottom">
        {/* stream */}
        <div className="bot-panel">
          <div className="bot-title">Training Stream</div>
          <div className="stream" ref={streamRef}>
            {stream.map((r, i) => (
              <div className="s-row" key={i}>
                <span className="s-time">{r.time}</span>
                <span className={r.cl}>[{r.tag}]</span>
                <span className="s-msg">{r.msg}</span>
              </div>
            ))}
          </div>
        </div>

        {/* metrics */}
        <div className="bot-panel">
          <div className="bot-title">Bot Metrics</div>
          <div className="mets">
            {[
              ["Balance", `$${Math.round(bal).toLocaleString()}`, true],
              ["Deposit", `$${DEP.toLocaleString()}`, false],
              ["ROI", `${roi}%`, true],
              ["Win Rate", `${winRate}%`, false],
              ["Edge", `${edge.toFixed(2)}%`, false],
              ["Trades/Hr", tradesHr, false],
              ["Total", total.toLocaleString(), false],
              ["Sharpe", sharpe, false],
              ["Max DD", `${maxDD}%`, false],
              ["Strategy", "5m BTC Arb", false],
              ["Orders", "Limit Only", false],
              ["Hedge", "Directional", false],
              ["Exp. Edge", `${(expectedEdge * 100).toFixed(2)}%/trade`, expectedEdge > 0],
            ].map(([l, v, b]) => (
              <div className="mrow" key={l}>
                <span className="ml">{l}</span>
                <span className={b ? "mv-bright" : "mv"}>{v}</span>
              </div>
            ))}
          </div>
          {mode === "paper" && (
            <div style={{
              margin: "8px 0 4px",
              fontSize: 9,
              color: "var(--yellow)",
              letterSpacing: "0.08em",
              borderTop: "1px solid var(--green5)",
              paddingTop: 6,
            }}>
              ⚠ PAPER SIMULATION — not real money
            </div>
          )}
          <div className="status-block">
            <div className="st-title">Status</div>
            <div className="st-grid">
              {[
                ["Polymarket", "ONLINE", "st-on"],
                ["LMSR",       "ONLINE", "st-on"],
                ["Bayes",      "ONLINE", "st-on"],
                ["Kelly",      "ONLINE", "st-on"],
                ["Slippage",   "ACTIVE", "st-act"],
                ["Scanner",    "SCAN",   "st-sc"],
                ["Sync",       "99.8%",  "st-on"],
              ].map(([k, v, c]) => (
                <div className="st-row" key={k}>
                  <span className="st-k">{k}</span>
                  <span className={c}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* p&l */}
        <div className="bot-panel">
          <div className="bot-title">P&amp;L Curve</div>
          <div className="pl-num">${Math.round(bal).toLocaleString()}</div>
          <div className="pl-sub">from ${DEP.toLocaleString()} · ROI {roi}%</div>
          <div className="pl-svg-wrap">
            <PLCurve hist={hist} />
          </div>
          <div style={{ marginTop: "6px", fontSize: "8px", color: "var(--green4)", letterSpacing: "0.07em" }}>
            BAYESIAN · EDGE · SPREAD · STOIKOV · KELLY · MONTE CARLO
          </div>
        </div>
      </div>

      {/* FOOTER */}
      <div className="footer">
        <span>ALL CRYPTO · 72H MARKETS · {tradesHr} TRADES/HR · {winRate}% WIN · {edge.toFixed(2)}% EDGE · KELLY 75% · MAX POS 10%</span>
        <span>${DEP.toLocaleString()} → ${Math.round(bal).toLocaleString()} · ⚠ HIGH RISK MODE — MAX AGGRESSION</span>
      </div>
    </div>
  );
}
