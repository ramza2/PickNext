from app.main import create_app


def test_create_app():
    app = create_app()
    assert app.title == "PickNext"
    assert "/api/v1/health" in app.openapi()["paths"]
