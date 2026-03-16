"""
api_server.py — FastAPI + WebSocket bridge between the HEISENBERG bot and the dashboard.

Endpoints:
  GET  /status   → current bot_state snapshot
  GET  /signals  → last 50 tradeable signals
  WS   /stream   → pushes bot_state every 1 second to all connected clients

Run with:
  uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import bot as bot_module
from bot import HeisenbergBot, PipelineSignal

load_dotenv()
logger = logging.getLogger("api_server")

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="HEISENBERG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Bot instance
# ---------------------------------------------------------------------------

_STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100"))
bot_instance = HeisenbergBot(bankroll=_STARTING_CAPITAL)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

bot_state: dict[str, Any] = {
    "balance": _STARTING_CAPITAL,
    "deposit": _STARTING_CAPITAL,
    "roi": 0.0,
    "win_rate": 0.0,
    "trades_hr": 0,
    "total_trades": 0,
    "sharpe": 0.0,
    "max_dd": 0.0,
    "edge": 0.0,
    "signals": [],
    "stream": [],
    "status": {
        "polymarket": "ONLINE",
        "bayes": "ONLINE",
        "kelly": "ONLINE",
        "scanner": "SCAN",
        "sync": "99.8%",
    },
}

# Rolling trackers for Sharpe / drawdown
_trade_returns: list[float] = []
_peak_balance: float = _STARTING_CAPITAL
_wins: int = 0
_losses: int = 0
_cycle_start: float = time.time()
_tradeable_count: int = 0  # across all cycles for trades/hr estimate
_edges: list[float] = []
_cycle_count: int = 0
_markets_last_cycle: int = 0

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()

# ---------------------------------------------------------------------------
# Paper trade simulation
# ---------------------------------------------------------------------------

def _simulate_trade(signal: PipelineSignal) -> None:
    """Simulate a paper trade outcome and update bot_state."""
    global _peak_balance, _wins, _losses, _tradeable_count

    balance = bot_state["balance"]
    size = min(signal.kelly_position_size, balance * 0.02)
    if size <= 0:
        return

    ask = signal.spread_data.ask   # market ask price we'd pay
    mid = signal.mid_price
    if ask <= 0 or ask >= 1 or mid <= 0 or mid >= 1:
        return

    # Win probability = market mid + our edge (bounded to reasonable range)
    net_edge = signal.edge_signal.net_edge
    win_prob = max(0.35, min(0.80, mid + net_edge * 5))

    if random.random() < win_prob:
        # YES resolves to 1.0: profit = size * (1/ask - 1)
        pnl = size * (1.0 / ask - 1.0)
        _wins += 1
    else:
        # NO resolves: lose the stake
        pnl = -size
        _losses += 1

    bot_state["balance"] = round(balance + pnl, 2)
    _tradeable_count += 1

    # Update peak / max drawdown
    if bot_state["balance"] > _peak_balance:
        _peak_balance = bot_state["balance"]
    drawdown = (_peak_balance - bot_state["balance"]) / _peak_balance * 100
    bot_state["max_dd"] = round(max(bot_state["max_dd"], drawdown), 2)

    # Rolling Sharpe (last 30 returns)
    _trade_returns.append(pnl / size)  # normalised return
    if len(_trade_returns) > 30:
        _trade_returns.pop(0)
    if len(_trade_returns) >= 4:
        arr = _trade_returns
        mean_r = sum(arr) / len(arr)
        std_r = math.sqrt(sum((x - mean_r) ** 2 for x in arr) / len(arr))
        bot_state["sharpe"] = round((mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0, 2)

    # Win rate
    total = _wins + _losses
    if total > 0:
        bot_state["win_rate"] = round(_wins / total * 100, 1)

    # ROI
    dep = bot_state["deposit"]
    bot_state["roi"] = round((bot_state["balance"] - dep) / dep * 100, 2)


def _format_time() -> str:
    now = datetime.now()
    return now.strftime("%H:%M:%S")


def _signal_to_stream(signal: PipelineSignal, tag: str, cl: str, msg: str) -> dict:
    return {"time": _format_time(), "tag": tag, "cl": cl, "msg": msg}


# ---------------------------------------------------------------------------
# Cycle callback (called by bot after each cycle)
# ---------------------------------------------------------------------------

def _on_cycle_complete(signals: list[PipelineSignal]) -> None:
    global _tradeable_count, _cycle_count, _markets_last_cycle
    _cycle_count += 1
    _markets_last_cycle = len(signals)

    if signals:
        z_vals = [s.edge_signal.z_score for s in signals]
        net_vals = [s.edge_signal.net_edge for s in signals]
        logger.info(
            "Cycle %d — %d tokens | z=[%.3f..%.3f] net=[%.4f..%.4f] | %d tradeable",
            _cycle_count, len(signals),
            min(z_vals), max(z_vals),
            min(net_vals), max(net_vals),
            sum(1 for s in signals if s.edge_signal.is_tradeable),
        )

    tradeable = [s for s in signals if s.edge_signal.is_tradeable]
    total_now = bot_state["total_trades"] + len(signals)
    bot_state["total_trades"] = total_now

    # Collect edges
    for s in signals:
        _edges.append(abs(s.edge_signal.net_edge))
    if len(_edges) > 100:
        _edges[:] = _edges[-100:]
    if _edges:
        bot_state["edge"] = round(sum(_edges) / len(_edges) * 100, 2)

    # Trades/hr estimate
    elapsed_hrs = max((time.time() - _cycle_start) / 3600, 1 / 3600)
    bot_state["trades_hr"] = min(int(_tradeable_count / elapsed_hrs), 999)

    # Paper-trade each tradeable signal
    for s in tradeable:
        _simulate_trade(s)

    # Build stream entries
    new_entries: list[dict] = []
    for s in signals[:8]:  # cap to avoid flood
        q_short = s.market_question[:30].strip()
        if s.edge_signal.is_tradeable:
            msg = f"{q_short} | z={s.edge_signal.z_score:+.3f} ev={s.edge_signal.expected_value:+.4f} size=${s.kelly_position_size:.2f}"
            new_entries.append({"time": _format_time(), "tag": "SIGNAL", "cl": "s-tag-g", "msg": msg})
        else:
            msg = f"{q_short} | z={s.edge_signal.z_score:+.3f} mid={s.mid_price:.3f} net={s.edge_signal.net_edge:+.4f}"
            new_entries.append({"time": _format_time(), "tag": "SKIP", "cl": "s-tag-b", "msg": msg})

    # Append SCAN heartbeat
    new_entries.append({
        "time": _format_time(),
        "tag": "SCAN",
        "cl": "s-tag-y",
        "msg": f"{len(signals)} tokens · {len(tradeable)} signals",
    })

    stream = bot_state["stream"]
    stream.extend(new_entries)
    bot_state["stream"] = stream[-100:]

    # Append tradeable signals to signals list
    for s in tradeable:
        bot_state["signals"].append({
            "token_id": s.token_id,
            "question": s.market_question[:60],
            "mid": s.mid_price,
            "z": s.edge_signal.z_score,
            "ev": s.edge_signal.expected_value,
            "edge": s.edge_signal.net_edge,
            "size": s.kelly_position_size,
            "time": _format_time(),
        })
    bot_state["signals"] = bot_state["signals"][-50:]


# Register callback with bot module
bot_module.on_cycle_complete = _on_cycle_complete

# ---------------------------------------------------------------------------
# WebSocket broadcaster
# ---------------------------------------------------------------------------

async def _broadcast_loop() -> None:
    """Push bot_state snapshot to all connected WS clients every 1 second."""
    while True:
        await asyncio.sleep(1)
        if not _ws_clients:
            continue
        payload = json.dumps(bot_state)
        dead: set[WebSocket] = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(bot_instance.run())
    asyncio.create_task(_broadcast_loop())
    logger.info("HEISENBERG API started. Bot running. Broadcaster running.")


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "cycles": _cycle_count,
        "markets": _markets_last_cycle,
        "balance": bot_state["balance"],
        "uptime_s": round(time.time() - _cycle_start),
    }


@app.get("/status")
async def get_status():
    return bot_state


@app.get("/signals")
async def get_signals():
    return bot_state["signals"][-50:]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/stream")
async def ws_stream(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    try:
        # Send current state immediately on connect
        await ws.send_text(json.dumps(bot_state))
        # Keep alive — bot broadcaster handles sends
        while True:
            await asyncio.sleep(30)
            await ws.send_text('{"ping":1}')
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _ws_clients.discard(ws)
