"""
order_executor.py — Polymarket Relayer API order placement.

Uses the Relayer API (POLY_RELAYER_API_KEY header) — no SDK, no signing required.

Safety guardrails:
  - $1.00 USDC hard cap per order
  - Max 3 simultaneous open positions
  - Auto-cancel orders older than 4 minutes
  - Balance floor: pause when balance < $40
  - Min net_edge > 0.05 AND ev > 0.01 AND spread <= 0.02
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CLOB_URL = "https://clob.polymarket.com"   # confirmed reachable from Railway
RELAYER_KEY = os.environ.get("POLY_RELAYER_API_KEY", "")

MAX_ORDER_SIZE = 1.00
MAX_POSITIONS = 3
ORDER_TTL_SECONDS = 240
BALANCE_FLOOR = 40.0
MIN_NET_EDGE = 0.05
MIN_EV = 0.01
MAX_SPREAD = 0.02


@dataclass
class OrderRequest:
    token_id: str
    side: str
    price: float
    size: float
    expiry_seconds: int = ORDER_TTL_SECONDS
    net_edge: float = 0.0
    ev: float = 0.0
    spread: float = 0.0


@dataclass
class OrderResult:
    order_id: str
    status: str
    token_id: str
    side: str
    price: float
    size: float
    message: str = ""


@dataclass
class OpenPosition:
    order_id: str
    token_id: str
    side: str
    price: float
    size: float
    placed_at: float = field(default_factory=time.time)


class OrderExecutor:

    def __init__(self) -> None:
        self._positions: dict[str, OpenPosition] = {}
        self._paused: bool = False
        self._ready: bool = False
        if RELAYER_KEY:
            logger.info("Relayer API key loaded — ready for live trading.")
        else:
            logger.warning("POLY_RELAYER_API_KEY not set — live trading disabled.")

    # ------------------------------------------------------------------
    # Startup probe (non-blocking — called as background task)
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.get(CLOB_URL + "/", follow_redirects=True)
                logger.info("CLOB endpoint reachable (HTTP %d).", resp.status_code)
                self._ready = bool(RELAYER_KEY)
                return self._ready
        except Exception as exc:
            logger.error("CLOB endpoint unreachable: %s", exc)
            self._ready = False
            return False

    def is_live_capable(self) -> bool:
        return self._ready and bool(RELAYER_KEY)

    # ------------------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------------------

    def open_position_count(self) -> int:
        return len(self._positions)

    def is_paused(self) -> bool:
        return self._paused

    def check_balance_floor(self, balance: float) -> bool:
        if balance < BALANCE_FLOOR:
            if not self._paused:
                logger.warning("BALANCE FLOOR: $%.2f < $%.2f — pausing.", balance, BALANCE_FLOOR)
                self._paused = True
            return False
        if self._paused:
            logger.info("Balance recovered to $%.2f — resuming.", balance)
            self._paused = False
        return True

    async def expire_old_orders(self) -> None:
        now = time.time()
        expired = [
            oid for oid, pos in list(self._positions.items())
            if now - pos.placed_at > ORDER_TTL_SECONDS
        ]
        for oid in expired:
            logger.info("Auto-cancelling stale order %s", oid)
            await self.cancel_order(oid)

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def place_order(self, req: OrderRequest) -> OrderResult:
        if not RELAYER_KEY:
            return OrderResult("", "paper", req.token_id, req.side, req.price, req.size,
                               "No Relayer key — paper mode.")
        if self._paused:
            return OrderResult("", "paused", req.token_id, req.side, req.price, req.size,
                               f"Paused — balance below ${BALANCE_FLOOR:.0f}.")
        if len(self._positions) >= MAX_POSITIONS:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"Max {MAX_POSITIONS} positions open.")
        if req.net_edge < MIN_NET_EDGE:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"net_edge {req.net_edge:.4f} < {MIN_NET_EDGE}")
        if req.ev < MIN_EV:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"ev {req.ev:.4f} < {MIN_EV}")
        if req.spread > MAX_SPREAD:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"spread {req.spread:.4f} > {MAX_SPREAD}")

        size = min(req.size, MAX_ORDER_SIZE)
        body = {
            "tokenId": req.token_id,
            "side": req.side.upper(),
            "price": round(req.price, 3),
            "size": round(size, 2),
            "orderType": "LIMIT",
            "timeInForce": "GTD",
            "expiration": int(time.time()) + req.expiry_seconds,
        }
        headers = {
            "Authorization": f"Bearer {RELAYER_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{CLOB_URL}/order", headers=headers, json=body)
            if resp.status_code == 200:
                data = resp.json()
                order_id = data.get("orderID") or data.get("orderId") or data.get("id", "")
                status = data.get("status", "live")
                if order_id:
                    self._positions[order_id] = OpenPosition(
                        order_id=order_id, token_id=req.token_id,
                        side=req.side, price=req.price, size=size,
                    )
                logger.info("LIVE ORDER: id=%s %s token=%s price=%.3f size=$%.2f",
                            order_id, req.side, req.token_id[:12], req.price, size)
                return OrderResult(order_id, status, req.token_id, req.side, req.price, size)
            else:
                msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error("Order failed: %s", msg)
                return OrderResult("", "error", req.token_id, req.side, req.price, size, msg)
        except Exception as exc:
            logger.error("place_order exception: %s", exc)
            return OrderResult("", "error", req.token_id, req.side, req.price, size, str(exc))

    def confirm_fill(self, order_id: str) -> None:
        self._positions.pop(order_id, None)

    async def cancel_order(self, order_id: str) -> bool:
        if not RELAYER_KEY or not order_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{CLOB_URL}/order/{order_id}",
                    headers={"Authorization": f"Bearer {RELAYER_KEY}"},
                )
            self._positions.pop(order_id, None)
            logger.info("Order cancelled — id=%s", order_id)
            return resp.status_code < 300
        except Exception as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return False

    async def cancel_all(self) -> int:
        # No-op on startup — Relayer auto-expires orders
        return 0
