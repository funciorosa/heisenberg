import httpx, os, time, logging
logger = logging.getLogger(__name__)

RELAYER_URL = "https://relayer-api.polymarket.com"
RELAYER_KEY = os.getenv("POLY_RELAYER_API_KEY", "")

async def place_order(token_id: str, side: str, price: float, size: float):
    if not RELAYER_KEY:
        logger.error("POLY_RELAYER_API_KEY not set")
        return None
    headers = {
        "RELAYER_API_KEY": RELAYER_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "tokenId": token_id,
        "side": side.upper(),
        "price": round(price, 3),
        "size": round(size, 2),
        "orderType": "LIMIT",
        "timeInForce": "GTD",
        "expiration": int(time.time()) + 240
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{RELAYER_URL}/order",
                headers=headers,
                json=body,
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"LIVE ORDER PLACED: id={data.get('id')} {side} {token_id[:12]} price={price} size=${size}")
                return data
            else:
                logger.error(f"Order failed {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logger.error(f"Order exception: {e}")
        return None

async def cancel_all():
    logger.info("cancel_all: no-op")
    return []

CLOB_READY = bool(RELAYER_KEY)
