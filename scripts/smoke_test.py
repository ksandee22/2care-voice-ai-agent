import asyncio
import os

os.environ.setdefault("MOCK_AI", "true")

from httpx import ASGITransport, AsyncClient

from backend.main import app


async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        print("health:", health.json())

        conv = await client.post(
            "/api/v1/conversation/text",
            json={"text": "Book appointment with cardiologist tomorrow", "patient_id": "demo1"},
        )
        data = conv.json()
        print("response:", data.get("response_text", "")[:120])
        print("latency:", data.get("latency"))


if __name__ == "__main__":
    asyncio.run(main())
