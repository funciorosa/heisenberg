"""
order_executor.py — Polymarket order placement via official py-clob-client SDK.

The SDK handles all signing, nonces, and CLOB API headers automatically.

Safety guardrails:
  - $1.00 USDC hard cap per order
  - Max 3 simultaneous open positions
  - Auto-cancel orders older than 4 minutes
  - Balance floor: pause when balance < $40
  - Min net_edge > 0.05 AND ev > 0.01 AND spread <= 0.02
  - Retry up to 3x on errors
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Hard safety limits
MAX_ORDER_SIZE = 1.00
MAX_POSITIONS = 3
ORDER_TTL_SECONDS = 240
BALANCE_FLOOR = 40.0
MIN_NET_EDGE = 0.05
MIN_EV = 0.01
MAX_SPREAD = 0.02
MAX_RETRIES = 3


@dataclass
class OrderRequest:
    token_id: str
    side: str           # "BUY" or "SELL"
    price: float        # limit price (0–1)
    size: float         # USDC amount
    expiry_seconds: int = ORDER_TTL_SECONDS
    net_edge: float = 0.0
    ev: float = 0.0
    spread: float = 0.0


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


def _make_clob_client():
    """Instantiate the official Polymarket ClobClient. Returns None if SDK unavailable."""
    try:
        from py_clob_client.client import ClobClient
        private_key = os.environ.get("POLY_PRIVATE_KEY", "")
        wallet = os.environ.get("POLY_WALLET_ADDRESS", os.environ.get("POLY_RELAYER_ADDRESS", ""))
        if not private_key:
            return None
        return ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,        # correct param name (not private_key=)
            chain_id=137,           # Polygon mainnet
            signature_type=0,       # L1 wallet-based auth
            funder=wallet,
        )
    except Exception as exc:
        logger.warning("ClobClient init failed: %s", exc)
        return None


class OrderExecutor:
    """
    Places limit orders via the official Polymarket py-clob-client SDK.
    Falls back to paper mode if SDK unavailable or private key not set.
    """

    def __init__(self) -> None:
        # Client is NOT created here — ClobClient.__init__ makes blocking HTTP calls.
        # It is created lazily inside initialize() which runs in a thread executor.
        self._client = None
        self._positions: dict[str, OpenPosition] = {}
        self._paused: bool = False

    # ------------------------------------------------------------------
    # Compatibility stub — called from api_server startup
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """
        Probe CLOB reachability, then instantiate ClobClient in a thread executor
        (the SDK makes blocking HTTP calls during __init__ — must not run on event loop).
        Returns True if live trading is ready.
        """
        import httpx
        # Step 1: quick TCP probe (non-blocking)
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.get("https://clob.polymarket.com/", follow_redirects=True)
                logger.info("CLOB endpoint reachable (HTTP %d).", resp.status_code)
        except Exception as exc:
            logger.error("CLOB endpoint unreachable: %s — paper mode.", exc)
            return False

        # Step 2: build ClobClient in a thread so blocking init calls don't stall uvicorn
        try:
            self._client = await asyncio.get_event_loop().run_in_executor(
                None, _make_clob_client
            )
        except Exception as exc:
            logger.error("ClobClient init failed: %s — paper mode.", exc)
            return False

        if self._client:
            logger.info("ClobClient ready — L1 auth active.")
            return True
        else:
            logger.warning("ClobClient unavailable — POLY_PRIVATE_KEY missing.")
            return False

    def is_live_capable(self) -> bool:
        return self._client is not None

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
        """Place a live limit order via the Polymarket CLOB SDK."""
        if not self._client:
            return OrderResult("", "paper", req.token_id, req.side, req.price, req.size,
                               "ClobClient unavailable — paper mode.")

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

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._submit_order_sync, req.token_id, req.side, req.price, size,
                    int(time.time()) + req.expiry_seconds,
                )
                order_id = result.get("orderID") or result.get("id", "")
                status = result.get("status", "live")
                if order_id:
                    self._positions[order_id] = OpenPosition(
                        order_id=order_id, token_id=req.token_id,
                        side=req.side, price=req.price, size=size,
                    )
                logger.info(
                    "LIVE ORDER: id=%s %s token=%s price=%.3f size=$%.2f",
                    order_id, req.side, req.token_id[:12], req.price, size,
                )
                return OrderResult(order_id, status, req.token_id, req.side, req.price, size)
            except Exception as exc:
                logger.warning("place_order attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(0.5 * attempt)

        return OrderResult("", "error", req.token_id, req.side, req.price, size,
                           "All retry attempts failed.")

    def _submit_order_sync(
        self, token_id: str, side: str, price: float, size: float, expiration: int
    ) -> dict:
        """Synchronous SDK call — runs in thread executor to avoid blocking event loop."""
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=BUY if side.upper() == "BUY" else SELL,
            fee_rate_bps=0,
            nonce=0,
            expiration=expiration,
        )
        signed_order = self._client.create_order(order_args)
        return self._client.post_order(signed_order, OrderType.GTC) or {}

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def confirm_fill(self, order_id: str) -> None:
        self._positions.pop(order_id, None)

    async def cancel_order(self, order_id: str) -> bool:
        if not self._client or not order_id:
            return False
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._client.cancel, order_id
            )
            self._positions.pop(order_id, None)
            logger.info("Order cancelled — id=%s", order_id)
            return True
        except Exception as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return False

    async def cancel_all(self) -> int:
        if not self._client:
            return 0
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._client.cancel_all
            )
            count = result.get("cancelled", 0) if isinstance(result, dict) else 0
            self._positions.clear()
            logger.info("Cancelled %d open orders.", count)
            return count
        except Exception as exc:
            logger.error("cancel_all failed: %s", exc)
            return 0
