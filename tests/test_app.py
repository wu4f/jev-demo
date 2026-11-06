from ipaddress import ip_network
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from typesafe_sdk import (
    SystemOneResponse,
    TypeSafeAPIError,
    TypeSafeAPITimeoutError,
    TypeSafeError,
)

import app as lab
from demos import DEMOS


@pytest.fixture(autouse=True)
def network_config(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(lab, "ALLOWED_NETWORK", ip_network("131.252.0.0/16"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-secret-not-for-browser")
    with TestClient(lab.app, base_url="http://localhost", client=("131.252.12.34", 1234)) as client:
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
    monkeypatch.setenv("K_SERVICE", "jev-lab")
    sdk.system_one.return_value = SystemOneResponse(
        model="jev-test",
        answers={
            name: answer_for(question) for name, question in DEMOS["support"].questions.items()
        },
        usage={},
    )
    with TestClient(lab.app, base_url="http://jev-lab.example") as remote:
        result = remote.post(
            "/api/demos/support/run",
            json={"text": "My checkout is broken"},
            headers={
                "origin": "https://jev-lab.example",
                "x-forwarded-proto": "https",
                "x-forwarded-for": "131.252.12.34",
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


@pytest.mark.parametrize(
    ("address", "allowed"),
    [
        ("131.252.0.0", True),
        ("131.252.255.255", True),
        ("131.251.255.255", False),
        ("131.253.0.0", False),
        ("127.0.0.1", False),
        ("2001:db8::1", False),
        ("::ffff:131.252.12.34", True),
        ("invalid", False),
    ],
)
def test_ip_status_and_api_enforcement(address, allowed, sdk, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with TestClient(lab.app, client=(address, 1234)) as visitor:
        page = visitor.get("/demos/support")
        assert page.status_code == 200
        expected_ip = "131.252.12.34" if address.startswith("::ffff:") else address
        if address == "invalid":
            expected_ip = "Unknown"
        assert f"<code>{expected_ip}</code>" in page.text
        assert ("network-allowed" if allowed else "network-denied") in page.text
        assert ("TypeSafe access allowed" if allowed else "TypeSafe access denied") in page.text
        assert f'"network_allowed": {str(allowed).lower()}' in page.text
        assert ('type="submit" disabled' in page.text) is not allowed
        assert page.headers["cache-control"] == "private, no-store"
        result = visitor.post("/api/demos/support/run", json={"text": "Test"})
        # Allowed visitors reach configuration checking; denied visitors do not.
        assert result.status_code == (503 if allowed else 403)
        if not allowed:
            assert "TypeSafe access denied" in result.json()["detail"]
        assert visitor.get("/health").status_code == 200
    lab.AsyncTypeSafeClient.assert_not_called()


def test_local_forwarding_headers_cannot_spoof_address(sdk):
    with TestClient(lab.app, client=("203.0.113.1", 1234)) as visitor:
        headers = {
            "x-forwarded-for": "131.252.12.34",
            "x-real-ip": "131.252.12.34",
            "forwarded": "for=131.252.12.34",
        }
        page = visitor.get("/", headers=headers)
        assert "203.0.113.1" in page.text
        assert "network-denied" in page.text
        assert (
            visitor.post(
                "/api/demos/support/run", json={"text": "Test"}, headers=headers
            ).status_code
            == 403
        )
    lab.AsyncTypeSafeClient.assert_not_called()


@pytest.mark.parametrize(
    ("forwarded_headers", "expected_ip"),
    [
        ([("x-forwarded-for", "131.252.12.34, 203.0.113.1")], "203.0.113.1"),
        (
            [("x-forwarded-for", "131.252.12.34"), ("x-forwarded-for", "203.0.113.1")],
            "203.0.113.1",
        ),
        ([("x-forwarded-for", "131.252.12.34, invalid")], "Unknown"),
        ([("x-forwarded-for", "131.252.12.34,")], "Unknown"),
        ([], "Unknown"),
    ],
)
def test_cloud_run_ignores_spoofed_prefix_and_fails_closed(
    sdk, monkeypatch, forwarded_headers, expected_ip
):
    monkeypatch.setenv("K_SERVICE", "jev-lab")
    with TestClient(lab.app, client=("131.252.99.99", 1234)) as visitor:
        page = visitor.get("/", headers=forwarded_headers)
        assert f"<code>{expected_ip}</code>" in page.text
        assert "network-denied" in page.text
        result = visitor.post(
            "/api/demos/support/run", json={"text": "Test"}, headers=forwarded_headers
        )
        assert result.status_code == 403
    lab.AsyncTypeSafeClient.assert_not_called()


def test_local_network_can_be_configured_for_development(sdk, monkeypatch):
    monkeypatch.setattr(lab, "ALLOWED_NETWORK", ip_network("127.0.0.0/8"))
    with TestClient(lab.app, client=("127.0.0.1", 1234)) as visitor:
        page = visitor.get("/")
    assert "network-allowed" in page.text
    assert "<code>127.0.0.1</code>" in page.text
    assert "<code>127.0.0.0/8</code>" in page.text


def test_missing_socket_address_is_denied(sdk):
    async def without_socket_address(scope, receive, send):
        scope["client"] = None
        await lab.app(scope, receive, send)

    with TestClient(without_socket_address) as visitor:
        page = visitor.get("/")
        assert "<code>Unknown</code>" in page.text
        assert "network-denied" in page.text
        result = visitor.post("/api/demos/support/run", json={"text": "Test"})
        assert result.status_code == 403
    lab.AsyncTypeSafeClient.assert_not_called()
