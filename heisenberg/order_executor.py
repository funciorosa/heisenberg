"""
order_executor.py — Polymarket order placement with endpoint auto-discovery.

Probes endpoints on startup, uses first reachable one, auto-falls back to
paper mode if all are unreachable.

Safety guardrails:
  - $1.00 USDC hard cap per order
  - Max 3 simultaneous open positions
  - Auto-cancel orders older than 4 minutes
  - Balance floor: pause when balance < $40
  - Min net_edge > 0.015 AND |z_score| > 1.0 to place order
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

# Endpoint probe order — first reachable wins
_CANDIDATE_BASES = [
    "https://clob.polymarket.com",
    "https://relayer-api.polymarket.com",
    "https://gamma-api.polymarket.com",
]

_DEFAULT_TIMEOUT = 10.0

# Hard safety limits
MAX_ORDER_SIZE = 1.00
MAX_POSITIONS = 3
ORDER_TTL_SECONDS = 240
BALANCE_FLOOR = 40.0
MIN_NET_EDGE = 0.015
MIN_Z_SCORE_LIVE = 1.0
MAX_RETRIES = 3


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
    status: str         # "live", "matched", "skipped", "paused", "error", "paper"
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
    Submits limit orders via Polymarket API.
    Auto-discovers working endpoint on startup; falls back to paper mode if none reachable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        relayer_address: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("POLY_RELAYER_API_KEY", "")
        self.relayer_address = relayer_address or os.environ.get("POLY_RELAYER_ADDRESS", "")
        self.base_url: str = _CANDIDATE_BASES[0]   # updated by initialize()
        self._reachable: bool = False               # set True after successful probe
        self._positions: dict[str, OpenPosition] = {}
        self._paused: bool = False
        if not self.api_key:
            logger.warning("POLY_RELAYER_API_KEY not set — live trading disabled.")

    # ------------------------------------------------------------------
    # Startup probe
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """
        Probe candidate endpoints; set self.base_url to first reachable one.
        Returns True if a working endpoint was found, False otherwise.
        Auto-switches to paper mode (sets self._reachable=False) if all fail.
        """
        for base in _CANDIDATE_BASES:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(base + "/", follow_redirects=True)
                    # Any HTTP response (even 404) means DNS + TCP work
                    self.base_url = base
                    self._reachable = True
                    logger.info("Polymarket endpoint reachable: %s (HTTP %d)", base, resp.status_code)
                    return True
            except Exception as exc:
                logger.warning("Endpoint probe failed for %s: %s", base, exc)

        logger.error(
            "POLYMARKET API UNREACHABLE — all endpoints failed DNS/TCP. "
            "Bot automatically switching to PAPER mode."
        )
        self._reachable = False
        return False

    def is_live_capable(self) -> bool:
        return self._reachable and bool(self.api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "POLY_API_KEY": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict, retries: int = MAX_RETRIES) -> dict:
        url = self.base_url + path
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
        url = self.base_url + path
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
        if balance < BALANCE_FLOOR:
            if not self._paused:
                logger.warning(
                    "BALANCE FLOOR: $%.2f < $%.2f — pausing live trading.",
                    balance, BALANCE_FLOOR,
                )
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
    # Public API
    # ------------------------------------------------------------------

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place a live limit order with full safety guardrails."""
        if not self._reachable or not self.api_key:
            return OrderResult("", "paper", req.token_id, req.side, req.price, req.size,
                               "API unreachable — paper mode active.")

        if self._paused:
            return OrderResult("", "paused", req.token_id, req.side, req.price, req.size,
                               f"Paused — balance below ${BALANCE_FLOOR:.0f} floor.")

        if len(self._positions) >= MAX_POSITIONS:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"Max {MAX_POSITIONS} positions open.")

        if req.net_edge < MIN_NET_EDGE:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"net_edge {req.net_edge:.4f} < {MIN_NET_EDGE}")

        if abs(req.z_score) < MIN_Z_SCORE_LIVE:
            return OrderResult("", "skipped", req.token_id, req.side, req.price, req.size,
                               f"|z| {abs(req.z_score):.3f} < {MIN_Z_SCORE_LIVE}")

        size = min(req.size, MAX_ORDER_SIZE)

        body = {
            "tokenId": req.token_id,
            "side": req.side.upper(),
            "price": str(round(req.price, 4)),
            "size": str(round(size, 2)),
            "expiration": req.expiry_seconds,
            "signerAddress": self.relayer_address,
            "orderType": "GTC",
        }

        try:
            data = await self._post("/order", body)
            order_id = data.get("orderID") or data.get("orderId") or data.get("id", "")
            status = data.get("status", "live")
            if order_id:
                self._positions[order_id] = OpenPosition(
                    order_id=order_id, token_id=req.token_id,
                    side=req.side, price=req.price, size=size,
                )
            logger.info(
                "LIVE ORDER: id=%s %s token=%s price=%.4f size=$%.2f via %s",
                order_id, req.side, req.token_id[:12], req.price, size, self.base_url,
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
        self._positions.pop(order_id, None)

    async def cancel_order(self, order_id: str) -> bool:
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
        if not self.api_key or not self._reachable:
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
