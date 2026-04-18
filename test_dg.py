import asyncio
import os
import json
from websockets import connect

url = "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1&model=nova-2&interim_results=true&endpointing=300"
api_key = "b5ef64e2b5a4791e4e85614335c0476d73a43dc8"

async def test():
    try:
        print("Connecting to Deepgram...", flush=True)
        ws = await connect(
            url,
            additional_headers={"Authorization": f"Token {api_key}"}
        )
        print("Connected successfully!", flush=True)
        await ws.close()
    except Exception as e:
        print(f"Error test 1: {e}", flush=True)
        
    try:
        print("Trying with extra_headers in case... ", flush=True)
        ws2 = await connect(
            url,
            extra_headers={"Authorization": f"Token {api_key}"}
        )
        print("Connected successfully! (extra_headers)", flush=True)
        await ws2.close()
    except Exception as e:
        print(f"Error test 2: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test())
