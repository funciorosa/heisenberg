"""
order_executor.py — Polymarket CLOB order placement via py-clob-client SDK.

Orders require EIP-712 signing — the SDK handles this automatically.
ClobClient is initialized in a background thread (it may make network calls)
so it never blocks uvicorn startup or the /health endpoint.

Safety guardrails:
  - $1.00 USDC hard cap per order
  - Max 3 simultaneous open positions
  - Auto-cancel orders older than 4 minutes
  - Balance floor: pause when balance < $40
  - Min net_edge > 0.05 AND ev > 0.01 AND spread <= 0.02
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

CLOB_URL = "https://clob.polymarket.com"

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


def _build_clob_client():
    """
    Synchronous — runs in thread executor.
    Builds ClobClient, loads or derives API credentials, returns ready client.
    Logs derived credentials so they can be saved to Railway env vars.
    """
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds

    private_key = os.environ.get("POLY_PRIVATE_KEY", "")
    wallet = os.environ.get("POLY_WALLET_ADDRESS", os.environ.get("POLY_RELAYER_ADDRESS", ""))

    if not private_key:
        logger.warning("POLY_PRIVATE_KEY not set — live trading unavailable.")
        return None

    client = ClobClient(
        host=CLOB_URL,
        key=private_key,
        chain_id=137,
        signature_type=0,   # L1 wallet-based auth
        funder=wallet,
    )

    api_key = os.environ.get("POLY_API_KEY", "")
    api_secret = os.environ.get("POLY_API_SECRET", "")
    api_passphrase = os.environ.get("POLY_API_PASSPHRASE", "")

    if api_key and api_secret and api_passphrase:
        client.set_api_creds(ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        ))
        logger.info("API credentials loaded from environment.")
    else:
        logger.info("Deriving API credentials from private key (one-time)...")
        creds = client.derive_api_key()
        logger.info("=== ADD THESE TO RAILWAY ENV VARS ===")
        logger.info("POLY_API_KEY=%s", creds.api_key)
        logger.info("POLY_API_SECRET=%s", creds.api_secret)
        logger.info("POLY_API_PASSPHRASE=%s", creds.api_passphrase)
        logger.info("=== THEN REDEPLOY TO STOP LOGGING SECRETS ===")
        client.set_api_creds(creds)

    return client


class OrderExecutor:

    def __init__(self) -> None:
        # Client built lazily in initialize() — never blocks startup
        self._client = None
        self._positions: dict[str, OpenPosition] = {}
        self._paused: bool = False

    async def initialize(self) -> bool:
        """Probe CLOB reachability then build client in thread. Called as background task."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                resp = await c.get(CLOB_URL + "/", follow_redirects=True)
                logger.info("CLOB endpoint reachable (HTTP %d).", resp.status_code)
        except Exception as exc:
            logger.error("CLOB unreachable: %s — paper mode.", exc)
            return False

        try:
            self._client = await asyncio.get_event_loop().run_in_executor(
                None, _build_clob_client
            )
        except Exception as exc:
            logger.error("ClobClient build failed: %s — paper mode.", exc)
            return False

        if self._client:
            logger.info("ClobClient ready — live orders enabled.")
            return True
        return False

    def is_live_capable(self) -> bool:
        return self._client is not None

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
        expired = [oid for oid, pos in list(self._positions.items())
                   if now - pos.placed_at > ORDER_TTL_SECONDS]
        for oid in expired:
            logger.info("Auto-cancelling stale order %s", oid)
            await self.cancel_order(oid)

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def place_order(self, req: OrderRequest) -> OrderResult:
        if not self._client:
            return OrderResult("", "paper", req.token_id, req.side, req.price, req.size,
                               "ClobClient not ready — paper mode.")
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
        expiration = int(time.time()) + req.expiry_seconds

        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._submit_sync, req.token_id, req.side, req.price, size, expiration
            )
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
        except Exception as exc:
            msg = str(exc)[:200]
            logger.error("place_order failed: %s", msg)
            return OrderResult("", "error", req.token_id, req.side, req.price, size, msg)

    def _submit_sync(self, token_id: str, side: str, price: float,
                     size: float, expiration: int) -> dict:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL
        args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=BUY if side.upper() == "BUY" else SELL,
            fee_rate_bps=0,
            nonce=0,
            expiration=expiration,
        )
        signed = self._client.create_order(args)
        return self._client.post_order(signed, OrderType.GTC) or {}

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
            logger.error("cancel_order failed: %s", exc)
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
            logger.info("Cancelled %d orders.", count)
            return count
        except Exception as exc:
            logger.error("cancel_all failed: %s", exc)
            return 0
