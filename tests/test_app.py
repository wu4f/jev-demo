from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from typesafe_sdk import (
    SystemOneResponse,
    TypeSafeAPIError,
    TypeSafeAPITimeoutError,
    TypeSafeError,
)
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import app as lab
from demos import DEMOS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-secret-not-for-browser")
    with TestClient(lab.app, base_url="http://localhost") as client:
        yield client


@pytest.fixture
def sdk(monkeypatch):
    instance = AsyncMock()
    factory = MagicMock(return_value=instance)
    instance.__aenter__.return_value = instance
    monkeypatch.setattr(lab, "AsyncTypeSafeClient", factory)
    return instance


def answer_for(question):
    if question.type == "choice":
        options = list(question.criteria)
        return {
            "type": "choice",
            "choice": options[0],
            "confidence": 1.0,
            "probabilities": {option: float(index == 0) for index, option in enumerate(options)},
        }
    if question.type == "score":
        return {
            "type": "score",
            "score": 0.0,
            "confidence": 1.0,
            "probabilities": {index: float(index == 0) for index in range(len(question.criteria))},
            "legend": dict(enumerate(question.criteria)),
        }
    return {"type": "noul", "noul": 0.8}


@pytest.mark.parametrize("slug", DEMOS)
def test_demo_page_and_real_sdk_serialization(client, sdk, slug):
    page = client.get(f"/demos/{slug}")
    assert page.status_code == 200
    assert DEMOS[slug].title in page.text
    assert "test-secret-not-for-browser" not in page.text
    sdk.system_one.return_value = SystemOneResponse(
        model="jev-test",
        answers={name: answer_for(question) for name, question in DEMOS[slug].questions.items()},
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    result = client.post(f"/api/demos/{slug}/run", json={"text": "Student example"})
    assert result.status_code == 200
    assert set(result.json()["response"]["answers"]) == set(DEMOS[slug].questions)
    assert result.json()["elapsed_ms"] >= 0
    assert "test-secret-not-for-browser" not in result.text
    sdk.system_one.assert_awaited_once_with(
        state="Student example", questions=DEMOS[slug].questions
    )


@pytest.mark.parametrize("text", ["", "  \n ", "x" * 6001])
def test_invalid_input_never_calls_api(client, sdk, text):
    assert client.post("/api/demos/support/run", json={"text": text}).status_code == 422
    sdk.system_one.assert_not_called()


def test_client_cannot_supply_arbitrary_questions(client, sdk):
    result = client.post(
        "/api/demos/support/run",
        json={"text": "Hello", "questions": {"anything": {"type": "noul"}}},
    )
    assert result.status_code == 422
    sdk.system_one.assert_not_called()


def test_missing_key_keeps_pages_available(client, sdk, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    assert client.get("/demos/support").status_code == 200
    result = client.post("/api/demos/support/run", json={"text": "Hello"})
    assert result.status_code == 503
    assert ".env" in result.json()["detail"]
    sdk.system_one.assert_not_called()


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (TypeSafeAPIError(401, "PRIVATE-UPSTREAM-DETAIL", {}), 502, "credentials"),
        (TypeSafeAPIError(429, "PRIVATE-UPSTREAM-DETAIL", {}), 429, "limit"),
        (TypeSafeAPIError(500, "PRIVATE-UPSTREAM-DETAIL", {}), 502, "could not complete"),
        (TypeSafeAPITimeoutError(20), 504, "timed out"),
        (TypeSafeError("PRIVATE-UPSTREAM-DETAIL"), 502, "configuration"),
    ],
)
def test_upstream_errors_are_explicit_and_sanitized(client, sdk, error, status, message):
    sdk.system_one.side_effect = error
    result = client.post("/api/demos/support/run", json={"text": "Hello"})
    assert result.status_code == status
    assert message in result.json()["detail"]
    assert "PRIVATE-UPSTREAM-DETAIL" not in result.text


def test_incomplete_response_is_not_a_success(client, sdk):
    sdk.system_one.return_value = SystemOneResponse(model="jev-test", answers={}, usage={})
    result = client.post("/api/demos/support/run", json={"text": "Hello"})
    assert result.status_code == 502


def test_unknown_demo_and_static_file_boundaries(client, sdk):
    assert client.get("/demos/unknown").status_code == 404
    assert client.post("/api/demos/unknown/run", json={"text": "Hello"}).status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/static/.env").status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    sdk.system_one.assert_not_called()


def test_cross_origin_call_rejected(client, sdk):
    result = client.post(
        "/api/demos/support/run", json={"text": "Hello"}, headers={"origin": "https://other.test"}
    )
    assert result.status_code == 403
    sdk.system_one.assert_not_called()


def test_cloud_run_forwarded_https_preserves_same_origin(sdk, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "injected-secret")
    sdk.system_one.return_value = SystemOneResponse(
        model="jev-test",
        answers={
            name: answer_for(question) for name, question in DEMOS["support"].questions.items()
        },
        usage={},
    )
    proxy_app = ProxyHeadersMiddleware(lab.app, trusted_hosts="*")
    with TestClient(proxy_app, base_url="http://jev-lab.example") as remote:
        result = remote.post(
            "/api/demos/support/run",
            json={"text": "My checkout is broken"},
            headers={
                "origin": "https://jev-lab.example",
                "x-forwarded-proto": "https",
                "x-forwarded-for": "203.0.113.1",
            },
        )
    assert result.status_code == 200
    assert "injected-secret" not in result.text
    sdk.system_one.assert_awaited_once()


def test_authenticated_local_proxy_needs_explicit_origin(client, sdk, monkeypatch):
    headers = {"origin": "http://127.0.0.1:8080"}
    assert (
        client.post("/api/demos/support/run", json={"text": "Test"}, headers=headers).status_code
        == 403
    )
    monkeypatch.setenv("JEV_PROXY_ORIGIN", "http://127.0.0.1:8080")
    sdk.system_one.return_value = SystemOneResponse(
        model="jev-test",
        answers={
            name: answer_for(question) for name, question in DEMOS["support"].questions.items()
        },
        usage={},
    )
    assert (
        client.post("/api/demos/support/run", json={"text": "Test"}, headers=headers).status_code
        == 200
    )
    page = client.get("/demos/support")
    assert 'href="/static/style.css"' in page.text
    assert 'src="/static/app.js"' in page.text
    assert (
        client.post(
            "/api/demos/support/run",
            json={"text": "Test"},
            headers={"origin": "http://127.0.0.1:8081"},
        ).status_code
        == 403
    )
