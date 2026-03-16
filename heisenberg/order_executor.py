"""
order_executor.py — Polymarket Relayer API order placement.

Safety guardrails:
  - $1.00 USDC hard cap per order
  - Max 3 simultaneous open positions
  - Auto-cancel orders older than 4 minutes
  - Balance floor: pause when balance < $40
  - Min net_edge > 0.015 AND z_score > 1.0 to place order
  - Retry up to 3x on API errors
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RELAYER_BASE = "https://relayer-api.polymarket.com"
_DEFAULT_TIMEOUT = 10.0

# Hard safety limits
MAX_ORDER_SIZE = 1.00        # $1.00 USDC hard cap
MAX_POSITIONS = 3            # max simultaneous open positions
ORDER_TTL_SECONDS = 240      # auto-cancel after 4 minutes
BALANCE_FLOOR = 40.0         # pause if balance drops below $40
MIN_NET_EDGE = 0.015         # minimum net_edge for live order
MIN_Z_SCORE_LIVE = 1.0       # minimum z_score for live order
MAX_RETRIES = 3              # retry attempts on transient API errors


@dataclass
class OrderRequest:
    token_id: str
    side: str           # "BUY" or "SELL"
    price: float        # limit price (0–1)
    size: float         # USDC amount
    expiry_seconds: int = ORDER_TTL_SECONDS
    net_edge: float = 0.0
    z_score: float = 0.0


@dataclass
class OrderResult:
    order_id: str
    status: str         # "live", "matched", "cancelled", "skipped", "paused", "error"
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
    """
    Submits and cancels limit orders via Polymarket's Relayer API.
    Tracks open positions, enforces safety limits, auto-cancels stale orders.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        relayer_address: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("POLY_RELAYER_API_KEY", "")
        self.relayer_address = relayer_address or os.environ.get("POLY_RELAYER_ADDRESS", "")
        self._positions: dict[str, OpenPosition] = {}   # order_id → position
        self._paused: bool = False
        if not self.api_key:
            logger.warning("POLY_RELAYER_API_KEY not set — live trading disabled.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "RELAYER_API_KEY": self.api_key,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict, retries: int = MAX_RETRIES) -> dict:
        url = RELAYER_BASE + path
        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = await client.post(url, json=body, headers=self._headers())
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(0.5 * attempt)
                    logger.warning("Retry %d/%d for POST %s: %s", attempt, retries, path, exc)
        raise last_exc

    async def _delete(self, path: str) -> dict:
        url = RELAYER_BASE + path
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.delete(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Position tracking & safety
    # ------------------------------------------------------------------

    def open_position_count(self) -> int:
        return len(self._positions)

    def is_paused(self) -> bool:
        return self._paused

    def check_balance_floor(self, balance: float) -> bool:
        """Returns True if trading may continue; False and sets pause if floor hit."""
        if balance < BALANCE_FLOOR:
            if not self._paused:
                logger.warning(
                    "BALANCE FLOOR: $%.2f < $%.2f — pausing live trading.",
                    balance, BALANCE_FLOOR,
                )
                self._paused = True
            return False
        # Recovered above floor — unpause
        if self._paused:
            logger.info("Balance recovered to $%.2f — resuming live trading.", balance)
            self._paused = False
        return True

    async def expire_old_orders(self) -> None:
        """Cancel and remove orders older than ORDER_TTL_SECONDS."""
        now = time.time()
        expired = [
            oid for oid, pos in list(self._positions.items())
            if now - pos.placed_at > ORDER_TTL_SECONDS
        ]
        for oid in expired:
            logger.info("Auto-cancelling stale order %s (>%ds old)", oid, ORDER_TTL_SECONDS)
            await self.cancel_order(oid)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place a live limit order with full safety guardrails."""
        # API key check
        if not self.api_key:
            return OrderResult("", "error", req.token_id, req.side, req.price, req.size,
                               "No API key configured.")

        # Paused (balance floor)
        if self._paused:
            return OrderResult("", "paused", req.token_id, req.side, req.price, req.size,
                               f"Paused — balance below ${BALANCE_FLOOR:.0f} floor.")

        # Position cap
        if len(self._positions) >= MAX_POSITIONS:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"Max {MAX_POSITIONS} positions already open.")

        # Edge gate
        if req.net_edge < MIN_NET_EDGE:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"net_edge {req.net_edge:.4f} < {MIN_NET_EDGE}")

        # Z-score gate
        if abs(req.z_score) < MIN_Z_SCORE_LIVE:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"|z_score| {abs(req.z_score):.3f} < {MIN_Z_SCORE_LIVE}")

        # Hard size cap
        size = min(req.size, MAX_ORDER_SIZE)

        body = {
            "tokenId": req.token_id,
            "side": req.side.upper(),
            "price": str(round(req.price, 4)),
            "size": str(round(size, 2)),
            "expiration": req.expiry_seconds,
            "signerAddress": self.relayer_address,
        }

        try:
            data = await self._post("/order", body)
            order_id = data.get("orderId") or data.get("id", "")
            status = data.get("status", "live")
            if order_id:
                self._positions[order_id] = OpenPosition(
                    order_id=order_id,
                    token_id=req.token_id,
                    side=req.side,
                    price=req.price,
                    size=size,
                )
            logger.info(
                "LIVE ORDER PLACED: id=%s %s token=%s price=%.4f size=$%.2f",
                order_id, req.side, req.token_id[:12], req.price, size,
            )
            return OrderResult(order_id, status, req.token_id, req.side, req.price, size)
        except httpx.HTTPStatusError as exc:
            msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.error("place_order failed: %s", msg)
            return OrderResult("", "error", req.token_id, req.side, req.price, size, msg)
        except Exception as exc:
            logger.error("place_order exception: %s", exc)
            return OrderResult("", "error", req.token_id, req.side, req.price, size, str(exc))

    def confirm_fill(self, order_id: str) -> None:
        """Remove a filled order from open positions."""
        self._positions.pop(order_id, None)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by ID. Returns True on success."""
        if not self.api_key or not order_id:
            return False
        try:
            await self._delete(f"/order/{order_id}")
            self._positions.pop(order_id, None)
            logger.info("Order cancelled — id=%s", order_id)
            return True
        except Exception as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return False

    async def cancel_all(self) -> int:
        """Cancel all open orders. Returns count cancelled."""
        if not self.api_key:
            return 0
        try:
            data = await self._delete("/orders")
            count = data.get("cancelled", 0)
            self._positions.clear()
            logger.info("Cancelled %d open orders.", count)
            return count
        except Exception as exc:
            logger.error("cancel_all failed: %s", exc)
            return 0
