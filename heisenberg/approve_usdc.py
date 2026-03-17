import asyncio
import os
from web3 import Web3

PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
WALLET = os.getenv("POLY_WALLET_ADDRESS", "")

POLYGON_RPCS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon-rpc.com",
]
USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1D45FE91671"
MAX = 2**256 - 1

ABI = [{"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]

def get_w3():
    for rpc in POLYGON_RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                print(f"Connected to RPC: {rpc}")
                return w3
            print(f"Not connected: {rpc}")
        except Exception as e:
            print(f"RPC error {rpc}: {e}")
    raise RuntimeError("No working Polygon RPC found")

def approve():
    w3 = get_w3()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"Wallet: {account.address}")
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC), abi=ABI)

    for spender_name, spender in [("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK", NEG_RISK_EXCHANGE)]:
        try:
            nonce = w3.eth.get_transaction_count(account.address)
            tx = usdc.functions.approve(
                Web3.to_checksum_address(spender), MAX
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 100000,
                "gasPrice": w3.to_wei("30", "gwei"),
                "chainId": 137,
            })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"Approved {spender_name}: {tx_hash.hex()}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            print(f"Confirmed {spender_name}: status={receipt.status}")
        except Exception as e:
            print(f"ERROR approving {spender_name}: {e}")

if __name__ == "__main__":
    approve()
