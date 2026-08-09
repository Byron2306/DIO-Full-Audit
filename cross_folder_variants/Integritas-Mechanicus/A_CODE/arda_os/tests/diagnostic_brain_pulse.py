import asyncio
import httpx
import json

async def test_brain():
    print("--- [AINUR DIAGNOSTIC PULSE] ---")
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": "You are Manwë. Answer in JSON with judgment LAWFUL and reason 'Diagnostic test'.",
        "stream": False,
        "format": "json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                body = response.json()
                print(f"Response: {body.get('response')}")
            else:
                print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_brain())
