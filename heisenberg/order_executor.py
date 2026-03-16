"""
order_executor.py — Polymarket Relayer API order placement.

All order placement goes through the Relayer API (no on-chain gas required).
Authentication uses a single RELAYER_API_KEY header.

Endpoint: https://relayer-api.polymarket.com
Docs: https://docs.polymarket.com/#relayer-api
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RELAYER_BASE = "https://relayer-api.polymarket.com"
_DEFAULT_TIMEOUT = 10.0


@dataclass
class OrderRequest:
    token_id: str
    side: str          # "BUY" or "SELL"
    price: float       # limit price (0–1)
    size: float        # USDC amount
    expiry_seconds: int = 240  # auto-cancel after 4 minutes


@dataclass
class OrderResult:
    order_id: str
    status: str        # "live", "matched", "cancelled", "error"
    token_id: str
    side: str
    price: float
    size: float
    message: str = ""


class OrderExecutor:
    """
    Submits and cancels limit orders via Polymarket's Relayer API.
    Requires POLY_RELAYER_API_KEY and POLY_RELAYER_ADDRESS in environment
    (or passed directly to __init__).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        relayer_address: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("POLY_RELAYER_API_KEY", "")
        self.relayer_address = relayer_address or os.environ.get("POLY_RELAYER_ADDRESS", "")
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

    async def _post(self, path: str, body: dict) -> dict:
        url = RELAYER_BASE + path
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def _delete(self, path: str) -> dict:
        url = RELAYER_BASE + path
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.delete(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place a limit order via the Relayer API."""
        if not self.api_key:
            return OrderResult(
                order_id="",
                status="error",
                token_id=req.token_id,
                side=req.side,
                price=req.price,
                size=req.size,
                message="No relayer API key configured.",
            )

        body = {
            "tokenId": req.token_id,
            "side": req.side.upper(),
            "price": str(round(req.price, 4)),
            "size": str(round(req.size, 2)),
            "expiration": req.expiry_seconds,
            "signerAddress": self.relayer_address,
        }

        try:
            data = await self._post("/order", body)
            order_id = data.get("orderId") or data.get("id", "")
            status = data.get("status", "live")
            logger.info(
                "Order placed — id=%s side=%s token=%s price=%.4f size=%.2f",
                order_id, req.side, req.token_id[:12], req.price, req.size,
            )
            return OrderResult(
                order_id=order_id,
                status=status,
                token_id=req.token_id,
                side=req.side,
                price=req.price,
                size=req.size,
            )
        except httpx.HTTPStatusError as exc:
            msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.error("place_order failed: %s", msg)
            return OrderResult(
                order_id="", status="error",
                token_id=req.token_id, side=req.side,
                price=req.price, size=req.size, message=msg,
            )
        except Exception as exc:
            logger.error("place_order exception: %s", exc)
            return OrderResult(
                order_id="", status="error",
                token_id=req.token_id, side=req.side,
                price=req.price, size=req.size, message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by ID. Returns True on success."""
        if not self.api_key or not order_id:
            return False
        try:
            await self._delete(f"/order/{order_id}")
            logger.info("Order cancelled — id=%s", order_id)
            return True
        except Exception as exc:
            logger.error("cancel_order failed for %s: %s", order_id, exc)
            return False

    async def cancel_all(self) -> int:
        """Cancel all open orders for this signer. Returns count cancelled."""
        if not self.api_key:
            return 0
        try:
            data = await self._delete("/orders")
            count = data.get("cancelled", 0)
            logger.info("Cancelled %d open orders.", count)
            return count
        except Exception as exc:
            logger.error("cancel_all failed: %s", exc)
            return 0
