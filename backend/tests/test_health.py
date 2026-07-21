from sqlalchemy import text
from sqlalchemy.orm import Session


def test_health_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok", "database": "connected"}


def test_database_connection(db: Session):
    result = db.execute(text("SELECT 1")).scalar_one()
    assert result == 1
