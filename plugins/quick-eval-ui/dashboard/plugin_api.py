"""why: dashboard backend, mounted by Hermes at /api/plugins/quick-eval-ui/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, Request  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402

import quickeval_routes as routes  # noqa: E402

router = APIRouter()


async def read_body(request):
    if request.method not in ("POST", "PUT"):
        return None
    try:
        return await request.json()
    except ValueError:
        return {}


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def quick_eval(request: Request, path: str):
    body = await read_body(request)
    status, payload = routes.handle(request.method, "/" + path, dict(request.query_params), body)
    if isinstance(payload, tuple):
        return PlainTextResponse(payload[1], media_type="application/x-ndjson")
    return JSONResponse(payload, status_code=status)
