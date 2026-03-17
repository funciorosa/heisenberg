import asyncio, logging, os, time
logger = logging.getLogger(__name__)

PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
CLOB_HOST   = "https://clob.polymarket.com"
CHAIN_ID    = 137
_client     = None
_lock       = asyncio.Lock()

async def _get_client():
    global _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is not None:
            return _client
        if not PRIVATE_KEY:
            logger.error("POLY_PRIVATE_KEY not set")
            return None
        try:
            from py_clob_client.client import ClobClient
            from eth_account import Account
            c = await asyncio.to_thread(
                ClobClient, CLOB_HOST,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                signature_type=2,
                funder=Account.from_key(PRIVATE_KEY).address,
            )
            # Get API credentials
            try:
                creds = await asyncio.to_thread(c.create_api_key)
                await asyncio.to_thread(c.set_api_creds, creds)
                logger.info("API creds created OK: key=%s", creds.api_key)
            except Exception as e1:
                logger.warning("create_api_key failed: %s — trying derive", e1)
                try:
                    creds = await asyncio.to_thread(c.derive_api_key)
                    await asyncio.to_thread(c.set_api_creds, creds)
                    logger.info("API creds derived OK: key=%s", creds.api_key)
                except Exception as e2:
                    logger.error("derive_api_key also failed: %s", e2)
                    return None
            _client = c
            logger.info("ClobClient ready")
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
            expiration=0,
        )
        signed = await asyncio.to_thread(client.create_order, args)
        result = await asyncio.to_thread(client.post_order, signed)
        logger.info("LIVE ORDER: %s %s price=%.3f size=$%.2f → %s",
                    side.upper(), token_id[:12], price, size, result)
        return result
    except Exception as e:
        logger.error("Order failed: %s", e)
        return None

async def _run_startup_allowance():
    client = await _get_client()
    if client:
        try:
            logger.info("Running update_balance_allowance...")
            result = await asyncio.to_thread(client.update_balance_allowance)
            logger.info("update_balance_allowance OK: %s", result)
        except Exception as e:
            logger.error("update_balance_allowance error: %s", e)
        try:
            logger.info("Running update_balance_allowance CONDITIONAL...")
            result2 = await asyncio.to_thread(client.update_balance_allowance, "CONDITIONAL")
            logger.info("update_balance_allowance CONDITIONAL OK: %s", result2)
        except Exception as e:
            logger.error("update_balance_allowance CONDITIONAL error: %s", e)

async def cancel_all():
    return []

CLOB_READY = bool(PRIVATE_KEY)
