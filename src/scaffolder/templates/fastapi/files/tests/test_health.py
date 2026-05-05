from httpx import AsyncClient


async def test_health(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
