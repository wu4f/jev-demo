import asyncio
import logging
import os
from dataclasses import dataclass
from ipaddress import IPv6Address, ip_address, ip_network
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typesafe_sdk import (
    AsyncTypeSafeClient,
    RetryPolicy,
    TypeSafeAPIError,
    TypeSafeAPITimeoutError,
    TypeSafeError,
)

from demos import DEMOS

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)
ALLOWED_NETWORK = ip_network(os.getenv("JEV_ALLOWED_NETWORK", "131.252.0.0/16"))
app = FastAPI(title="Jev Lab")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@dataclass(frozen=True)
class NetworkAccess:
    client_ip: str | None
    allowed: bool


@app.middleware("http")
async def identify_client(request: Request, call_next):
    raw_ip = request.client.host if request.client else None
    if os.getenv("K_SERVICE"):
        # Direct Cloud Run ingress appends the connecting client after user-supplied entries.
        # Never authorize using Uvicorn's wildcard-trusted, leftmost forwarded address.
        forwarded = request.headers.getlist("x-forwarded-for")
        raw_ip = forwarded[-1].rsplit(",", 1)[-1].strip() if forwarded else None
        if request.headers.get("x-forwarded-proto") == "https":
            request.scope["scheme"] = "https"
    try:
        address = ip_address(raw_ip) if raw_ip else None
    except ValueError:
        address = None
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    request.state.network_access = NetworkAccess(
        client_ip=str(address) if address else None,
        allowed=address is not None and address in ALLOWED_NETWORK,
    )
    response = await call_next(request)
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "private, no-store"
    return response


def access_context(request: Request) -> dict[str, NetworkAccess]:
    return {"network_access": request.state.network_access}


templates = Jinja2Templates(directory=ROOT / "templates", context_processors=[access_context])


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=6000)

    @field_validator("text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter some text to evaluate.")
        return value


def current_model() -> str:
    return os.getenv("TYPESAFE_DEFAULT_MODEL", "").strip() or "jev-latest"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"demos": DEMOS.values()},
    )


@app.get("/demos/{slug}", response_class=HTMLResponse)
async def demo_page(request: Request, slug: str):
    if slug not in DEMOS:
        raise HTTPException(404, "Demo not found.")
    demo = DEMOS[slug]
    return templates.TemplateResponse(
        request=request,
        name="demo.html",
        context={
            "demos": DEMOS.values(),
            "demo": demo,
            "configured": bool(os.getenv("TYPESAFE_API_KEY", "").strip()),
            "config": {
                "slug": slug,
                "model": current_model(),
                "network_allowed": request.state.network_access.allowed,
                "questions": {
                    name: question.model_dump(mode="json", exclude_none=True)
                    for name, question in demo.questions.items()
                },
                "examples": [{"label": e.label, "text": e.text} for e in demo.examples],
            },
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/demos/{slug}/run")
async def run_demo(request: Request, slug: str, payload: RunInput):
    if slug not in DEMOS:
        raise HTTPException(404, "Demo not found.")
    access = request.state.network_access
    if not access.allowed:
        raise HTTPException(
            403,
            f"TypeSafe access denied for IP {access.client_ip or 'unknown'}. "
            "Connect from an authorized network or VPN.",
        )
    # Same-origin browser calls work locally and behind Cloud Run's TLS proxy.
    origin = request.headers.get("origin")
    allowed_origins = {str(request.base_url).rstrip("/")}
    proxy_origin = os.getenv("JEV_PROXY_ORIGIN", "").strip()
    if proxy_origin:
        allowed_origins.add(proxy_origin.rstrip("/"))
    if origin and origin not in allowed_origins:
        raise HTTPException(403, "Run experiments from this app's own page.")
    key = os.getenv("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            503,
            "Configure TYPESAFE_API_KEY via .env locally or a Secret Manager binding "
            "on Cloud Run, then restart or redeploy.",
        )

    started = perf_counter()
    try:
        async with AsyncTypeSafeClient(
            api_key=key,
            model=current_model(),
            timeout=20,
            retry=RetryPolicy(max_retries=0),
        ) as client:
            response = await asyncio.wait_for(
                client.system_one(state=payload.text, questions=DEMOS[slug].questions),
                timeout=25,
            )
    except (asyncio.TimeoutError, TypeSafeAPITimeoutError) as error:
        logger.warning("Jev request timed out")
        raise HTTPException(504, "Jev timed out. You can try again.") from error
    except TypeSafeAPIError as error:
        logger.warning("Jev returned HTTP %s", error.status)
        if error.status in (401, 403):
            message = "TypeSafe rejected the API credentials. Check your .env key and API access."
        elif error.status == 429:
            message = "TypeSafe's rate or usage limit was reached. Wait before trying again."
        else:
            message = "TypeSafe could not complete this request. Check the model and try again."
        raise HTTPException(429 if error.status == 429 else 502, message) from error
    except TypeSafeError as error:
        logger.warning("Jev SDK failure: %s", type(error).__name__)
        raise HTTPException(
            502, "Could not call Jev. Check your API configuration and network connection."
        ) from error

    if set(response.answers) != set(DEMOS[slug].questions):
        logger.warning("Jev response did not contain the expected answers")
        raise HTTPException(502, "Jev returned an incomplete response. Try again.")
    return {
        "response": response.model_dump(mode="json"),
        "elapsed_ms": round((perf_counter() - started) * 1000),
    }
