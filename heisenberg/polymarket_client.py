"""
polymarket_client.py — Read-only async client for the Polymarket CLOB API.

Project HEISENBERG — arbitrage bot data layer.
No authentication, no trading, no wallet interaction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://clob.polymarket.com"
GAMMA_URL = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT = 10.0          # seconds per request
MAX_RETRIES = 3
BACKOFF_BASE = 1.0              # seconds; doubles each retry
RATE_LIMIT_BACKOFF = 60.0       # seconds to wait on 429


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PriceLevel:
    """A single price/size entry on one side of an order book."""

    price: float
    size: float


@dataclass
class OrderBook:
    """Full order book snapshot for one Polymarket token."""

    token_id: str
    bids: list[PriceLevel] = field(default_factory=list)
    asks: list[PriceLevel] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def best_bid(self) -> float | None:
        """Return the highest bid price, or None if the book is empty."""
        if not self.bids:
            return None
        return max(pl.price for pl in self.bids)

    @property
    def best_ask(self) -> float | None:
        """Return the lowest ask price, or None if the book is empty."""
        if not self.asks:
            return None
        return min(pl.price for pl in self.asks)

    @property
    def mid_price(self) -> float | None:
        """Return the mid-point between best bid and best ask, or None."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    @property
    def spread(self) -> float | None:
        """Return ask − bid spread, or None if either side is empty."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return ask - bid


@dataclass
class MarketInfo:
    """High-level metadata for a Polymarket prediction market."""

    condition_id: str
    question: str
    end_date: str | None
    volume: float
    active: bool
    tokens: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CLOBTick:
    """A single CLOB historical price tick."""

    timestamp: int
    price: float
    volume: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_price_levels(raw_levels: list[dict[str, Any]]) -> list[PriceLevel]:
    """Convert raw API list of {price, size} dicts to PriceLevel objects.

    Silently skips any malformed entries.
    """
    levels: list[PriceLevel] = []
    for entry in raw_levels:
        try:
            price = float(entry["price"])
            size = float(entry["size"])
            levels.append(PriceLevel(price=price, size=size))
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Skipping malformed price level %s: %s", entry, exc)
    return levels


def _parse_market_info(raw: dict[str, Any]) -> MarketInfo:
    """Construct a MarketInfo from a raw /markets API response item."""
    return MarketInfo(
        condition_id=raw.get("condition_id", ""),
        question=raw.get("question", raw.get("title", "")),
        end_date=raw.get("end_date_iso") or raw.get("end_date"),
        volume=float(raw.get("volume", 0) or 0),
        active=bool(raw.get("active", True)),
        tokens=raw.get("tokens", []),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class PolymarketCLOBClient:
    """Async, read-only client for the Polymarket Central Limit Order Book API.

    All methods are coroutines and should be awaited.  The client manages a
    single underlying ``httpx.AsyncClient`` that is created lazily and reused
    across calls.  Use the async context manager to ensure the underlying
    transport is closed properly::

        async with PolymarketCLOBClient() as client:
            book = await client.fetch_orderbook(token_id="0xabc...")
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        backoff_base: float = BACKOFF_BASE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "PolymarketCLOBClient":
        await self._get_client()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or lazily create) the shared AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP transport."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Low-level request helper with retry + rate-limit handling
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an authenticated-free GET request with retry logic.

        Retries up to ``self.max_retries`` times using exponential back-off.
        A 429 response triggers a longer wait (``RATE_LIMIT_BACKOFF`` seconds)
        before the next attempt.  Non-retryable 4xx errors raise immediately.

        Parameters
        ----------
        path:
            URL path relative to ``self.base_url``.
        params:
            Optional query-string parameters.

        Returns
        -------
        Parsed JSON body (dict or list).

        Raises
        ------
        httpx.HTTPStatusError
            When the server returns a non-success status that is not retried.
        httpx.RequestError
            On network / timeout failures after all retries are exhausted.
        """
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.get(path, params=params)

                if response.status_code == 429:
                    wait = RATE_LIMIT_BACKOFF
                    logger.warning(
                        "Rate limited (429) on %s — waiting %.0fs (attempt %d/%d)",
                        path, wait, attempt + 1, self.max_retries + 1,
                    )
                    await asyncio.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        "429 rate limited", request=response.request, response=response
                    )
                    continue

                if response.status_code >= 500:
                    wait = self.backoff_base * (2 ** attempt)
                    logger.warning(
                        "Server error %d on %s — backing off %.1fs (attempt %d/%d)",
                        response.status_code, path, wait, attempt + 1, self.max_retries + 1,
                    )
                    await asyncio.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        f"{response.status_code} server error",
                        request=response.request,
                        response=response,
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                wait = self.backoff_base * (2 ** attempt)
                logger.warning(
                    "Network error on %s — backing off %.1fs (attempt %d/%d): %s",
                    path, wait, attempt + 1, self.max_retries + 1, exc,
                )
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def fetch_orderbook(self, token_id: str) -> OrderBook:
        """Fetch the live order book for a single Polymarket token.

        Parameters
        ----------
        token_id:
            The decimal token ID as returned by the Gamma API clobTokenIds field.

        Returns
        -------
        OrderBook
            Snapshot containing bids and asks sorted as returned by the API.
        """
        data = await self._get("/book", params={"token_id": token_id})
        bids = _parse_price_levels(data.get("bids", []))
        asks = _parse_price_levels(data.get("asks", []))
        return OrderBook(token_id=token_id, bids=bids, asks=asks)

    async def fetch_best_prices(self, token_id: str) -> dict[str, float | None]:
        """Return best bid and ask prices for a token.

        Parameters
        ----------
        token_id:
            The hex token ID to query.

        Returns
        -------
        dict with keys ``"bid"``, ``"ask"``, and ``"mid"``.
        """
        book = await self.fetch_orderbook(token_id)
        return {
            "bid": book.best_bid,
            "ask": book.best_ask,
            "mid": book.mid_price,
        }

    async def fetch_market_info(self, condition_id: str) -> MarketInfo | None:
        """Fetch metadata for a single market by its condition ID.

        Parameters
        ----------
        condition_id:
            The Polymarket condition ID (hex string).

        Returns
        -------
        MarketInfo or None if the market is not found.
        """
        data = await self._get("/markets", params={"condition_id": condition_id})
        # The endpoint may return a dict with a "data" key or a bare list
        items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            items = data.get("data", [data])
        elif isinstance(data, list):
            items = data

        if not items:
            logger.info("No market found for condition_id=%s", condition_id)
            return None

        return _parse_market_info(items[0])

    async def search_markets(
        self,
        query: str,
        limit: int = 100,
        active_only: bool = True,
    ) -> list[MarketInfo]:
        """Search markets by keyword.

        Parameters
        ----------
        query:
            Search string (e.g. ``"BTC"``, ``"Bitcoin"``, ``"ETH price"``).
        limit:
            Maximum number of results to return (server-side paging).
        active_only:
            When True, only return markets where ``active == True``.

        Returns
        -------
        list of MarketInfo objects.
        """
        params: dict[str, Any] = {"search": query, "limit": limit, "active": "true"}
        data = await self._get("/markets", params=params)

        raw_items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            raw_items = data.get("data", [])
        elif isinstance(data, list):
            raw_items = data

        markets = [_parse_market_info(item) for item in raw_items]
        if active_only:
            markets = [m for m in markets if m.active]
        return markets

    async def _gamma_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET against the Gamma API (market discovery) using a one-shot client."""
        url = GAMMA_URL.rstrip("/") + path
        async with httpx.AsyncClient(timeout=self.timeout, headers={"Accept": "application/json"}) as c:
            response = await c.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_btc_markets(self) -> list[MarketInfo]:
        """Fetch active BTC/Bitcoin prediction markets via the Gamma API.

        Uses gamma-api.polymarket.com/events with tag_slug=crypto, then
        filters for Bitcoin-related markets.  Falls back to CLOB search
        if the Gamma API is unavailable.

        Returns
        -------
        list of MarketInfo representing live BTC markets.
        """
        btc_kws = ("btc", "bitcoin")
        results: list[MarketInfo] = []
        seen: set[str] = set()

        try:
            # Pull crypto events — each event contains multiple correlated markets
            data = await self._gamma_get(
                "/events",
                params={"closed": "false", "limit": 100, "tag_slug": "crypto"},
            )
            events = data if isinstance(data, list) else data.get("data", [])
            for event in events:
                for mkt in event.get("markets", []):
                    question = mkt.get("question") or mkt.get("title") or ""
                    if not any(kw in question.lower() for kw in btc_kws):
                        continue
                    # Only include markets that currently accept orders on the CLOB
                    if not mkt.get("acceptingOrders", False):
                        continue
                    cid = mkt.get("conditionId") or mkt.get("condition_id") or ""
                    if cid in seen:
                        continue
                    seen.add(cid)
                    # clobTokenIds is the live token list from Gamma API
                    raw_token_ids = mkt.get("clobTokenIds") or mkt.get("tokens") or []
                    if isinstance(raw_token_ids, str):
                        import json as _json
                        try:
                            raw_token_ids = _json.loads(raw_token_ids)
                        except Exception:
                            raw_token_ids = []
                    tokens = [{"token_id": tid} for tid in raw_token_ids if isinstance(tid, str)]
                    results.append(MarketInfo(
                        condition_id=cid,
                        question=question,
                        end_date=mkt.get("endDateIso") or mkt.get("endDate"),
                        volume=float(mkt.get("volumeNum") or mkt.get("volume") or 0),
                        active=not mkt.get("closed", False),
                        tokens=tokens,
                        raw=mkt,
                    ))
        except Exception as exc:
            logger.warning("Gamma API unavailable (%s) — falling back to CLOB search", exc)
            # Fallback: CLOB text search
            for term in ("Bitcoin", "BTC"):
                try:
                    for m in await self.search_markets(term, active_only=True):
                        if m.condition_id not in seen and any(kw in m.question.lower() for kw in btc_kws):
                            seen.add(m.condition_id)
                            results.append(m)
                except Exception as e2:
                    logger.warning("CLOB search(%r) failed: %s", term, e2)

        logger.info("fetch_btc_markets: %d live BTC markets found", len(results))
        return results

    async def fetch_btc_5min_markets(self) -> list[MarketInfo]:
        """Return BTC markets best suited for short-horizon scanning.

        Polymarket does not currently offer sub-hour BTC resolution markets.
        This method returns all active BTC price prediction markets so the
        HEISENBERG pipeline still has data to process.  If explicit 5-min
        markets appear in future, the keyword filter will pick them up first.

        Returns
        -------
        list of MarketInfo for BTC markets.
        """
        all_btc = await self.fetch_btc_markets()

        # Prefer explicit short-interval markets if they exist
        short_kws = ("5-minute", "5 minute", "5min", "hourly", "1-hour", "1 hour")
        short = [m for m in all_btc if any(kw in m.question.lower() for kw in short_kws)]
        if short:
            logger.info("fetch_btc_5min_markets: %d short-interval markets", len(short))
            return short

        logger.info(
            "fetch_btc_5min_markets: no short-interval markets — scanning all %d BTC markets",
            len(all_btc),
        )
        return all_btc

    async def fetch_mid_prices(self, token_ids: list[str]) -> dict[str, float]:
        """Fetch mid-point prices for a batch of tokens.

        Parameters
        ----------
        token_ids:
            List of hex token IDs.

        Returns
        -------
        dict mapping each token_id to its mid price.
        """
        params = {"token_id": ",".join(token_ids)}
        data = await self._get("/midpoints", params=params)

        result: dict[str, float] = {}
        if isinstance(data, dict):
            for token_id, price_val in data.items():
                try:
                    result[token_id] = float(price_val)
                except (TypeError, ValueError):
                    pass
        return result

    async def fetch_spread(self, token_id: str) -> dict[str, float | None]:
        """Fetch the current bid-ask spread info for a token.

        Parameters
        ----------
        token_id:
            The hex token ID to query.

        Returns
        -------
        dict with keys ``"bid"``, ``"ask"``, ``"spread"``.
        """
        data = await self._get("/spread", params={"token_id": token_id})
        try:
            bid = float(data.get("bid", 0) or 0) if data else None
            ask = float(data.get("ask", 0) or 0) if data else None
            spread = float(data.get("spread", 0) or 0) if data else None
        except (TypeError, ValueError):
            bid = ask = spread = None
        return {"bid": bid, "ask": ask, "spread": spread}

    async def fetch_tick_size(self, token_id: str) -> float | None:
        """Fetch the minimum tick size for a given token.

        Parameters
        ----------
        token_id:
            The hex token ID to query.

        Returns
        -------
        Tick size as a float, or None if unavailable.
        """
        data = await self._get("/tick-size", params={"token_id": token_id})
        try:
            return float(data.get("minimum_tick_size") or data.get("tick_size") or 0) or None
        except (TypeError, ValueError, AttributeError):
            return None

    async def fetch_price_history(
        self,
        market: str,
        start_ts: int,
        end_ts: int,
        fidelity: int = 60,
    ) -> list[CLOBTick]:
        """Fetch historical price data for a market token.

        Parameters
        ----------
        market:
            Token ID or market identifier for the ``/prices-history`` endpoint.
        start_ts:
            Unix timestamp (seconds) for the start of the range.
        end_ts:
            Unix timestamp (seconds) for the end of the range.
        fidelity:
            Candle granularity in seconds (default 60 = 1 minute).

        Returns
        -------
        list of CLOBTick objects ordered by timestamp ascending.
        """
        params = {
            "market": market,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity,
        }
        data = await self._get("/prices-history", params=params)

        raw_history: list[dict[str, Any]] = []
        if isinstance(data, dict):
            raw_history = data.get("history", data.get("data", []))
        elif isinstance(data, list):
            raw_history = data

        ticks: list[CLOBTick] = []
        for entry in raw_history:
            try:
                ticks.append(
                    CLOBTick(
                        timestamp=int(entry.get("t", entry.get("timestamp", 0))),
                        price=float(entry.get("p", entry.get("price", 0))),
                        volume=float(entry.get("v", entry.get("volume", 0)) or 0),
                    )
                )
            except (TypeError, ValueError, KeyError) as exc:
                logger.debug("Skipping malformed tick %s: %s", entry, exc)

        return sorted(ticks, key=lambda t: t.timestamp)
