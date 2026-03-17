import asyncio, logging, os, time
logger = logging.getLogger(__name__)

PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
CLOB_HOST   = "https://clob.polymarket.com"
CHAIN_ID    = 137

_client     = None
_lock       = asyncio.Lock()


async def _get_client():
    """Lazily init ClobClient on first order — never blocks startup."""
    global _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is not None:
            return _client
        if not PRIVATE_KEY:
            logger.error("POLY_PRIVATE_KEY not set — cannot place orders")
            return None
        try:
            from py_clob_client.client import ClobClient
            c = await asyncio.to_thread(
                ClobClient,
                CLOB_HOST,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                signature_type=0,   # EOA — uses private key directly
            )
            _client = c
            logger.info("ClobClient ready (EOA signing, chain=%d)", CHAIN_ID)
        except Exception as e:
            logger.error("ClobClient init failed: %s", e)
            return None
    return _client


async def place_order(token_id: str, side: str, price: float, size: float):
    client = await _get_client()
    if not client:
        return None
    try:
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY, SELL

        args = OrderArgs(
            token_id=token_id,
            price=round(price, 3),
            size=round(size, 2),
            side=BUY if side.upper() == "BUY" else SELL,
            expiration=int(time.time()) + 240,
        )
        signed = await asyncio.to_thread(client.create_order, args)
        result = await asyncio.to_thread(client.post_order, signed)
        logger.info(
            "LIVE ORDER: %s %s price=%.3f size=$%.2f → %s",
            side.upper(), token_id[:12], price, size, result,
        )
        return result
    except Exception as e:
        logger.error("Order failed: %s", e)
        return None


async def cancel_all():
    logger.info("cancel_all: no-op")
    return []


CLOB_READY = bool(PRIVATE_KEY)
