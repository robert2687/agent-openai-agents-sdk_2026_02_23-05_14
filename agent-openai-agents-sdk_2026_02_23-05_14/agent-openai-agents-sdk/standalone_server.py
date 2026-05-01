"""
Standalone FastAPI server for PREVIEW.html — no mlflow/databricks dependencies.
Serves GET /health and POST /v1/chat/completions (streaming + non-streaming).
Reads OPENAI_API_KEY and OPENROUTER_API_KEY from .env.
"""
import json
import os
import logging
from pathlib import Path
from uuid import uuid4
from typing import AsyncGenerator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ── Load .env ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
PORT              = int(os.getenv("API_PORT", "8000"))
APP_NAME          = os.getenv("APP_NAME", "PERFECT-AGENT")
APP_URL           = os.getenv("APP_URL", "https://github.com/robert2687")

# Auto-select backend
if OPENROUTER_API_KEY and OPENROUTER_API_KEY not in ("your-openrouter-key", ""):
    BACKEND    = "openrouter"
    API_KEY    = OPENROUTER_API_KEY
    BASE_URL   = "https://openrouter.ai/api/v1"
    MODEL      = os.getenv("AGENT_MODEL", "tencent/hy3-preview:free")
elif OPENAI_API_KEY and OPENAI_API_KEY not in ("your-openai-key", ""):
    BACKEND    = "openai"
    API_KEY    = OPENAI_API_KEY
    BASE_URL   = "https://api.openai.com/v1"
    MODEL      = os.getenv("AGENT_MODEL", "gpt-4.1-mini")
else:
    BACKEND    = "none"
    API_KEY    = ""
    BASE_URL   = ""
    MODEL      = os.getenv("AGENT_MODEL", "gpt-4.1-mini")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("standalone_server")
LOGGER.info(
    "Backend: %s | Model: %s | Port: %d | EnvFile: %s",
    BACKEND,
    MODEL,
    PORT,
    ENV_FILE,
)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="Agent Server (standalone)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "backend": BACKEND,
        "model": MODEL,
        "fallback_model": None,
        "max_retries": 3,
        "retry_base_seconds": 1.5,
        "env_file": str(ENV_FILE),
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = str(uuid4())
    body = await request.json()
    stream = body.get("stream", False)
    messages = body.get("messages", [])
    model = body.get("model", MODEL)
    max_tokens = body.get("max_tokens", 2048)

    if BACKEND == "none":
        error_body = {
            "error": {
                "message": "No API key configured. Set OPENAI_API_KEY or OPENROUTER_API_KEY in .env",
                "type": "configuration_error",
                "request_id": request_id,
            }
        }
        return JSONResponse(content=error_body, status_code=503)

    try:
        from openai import AsyncOpenAI, APIStatusError, AuthenticationError

        client = AsyncOpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            default_headers={
                "HTTP-Referer": APP_URL,
                "X-OpenRouter-Title": APP_NAME,
            },
        )

        if stream:
            async def event_stream() -> AsyncGenerator[bytes, None]:
                try:
                    async with client.chat.completions.stream(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                    ) as stream_ctx:
                        async for event in stream_ctx:
                            chunk_dict = event.model_dump(exclude_unset=False)
                            # Only forward delta chunks with choices
                            if chunk_dict.get("choices"):
                                yield f"data: {json.dumps(chunk_dict)}\n\n".encode()
                except Exception as exc:
                    err = {
                        "error": {
                            "message": str(exc),
                            "type": "api_error",
                            "request_id": request_id,
                        }
                    }
                    yield f"data: {json.dumps(err)}\n\n".encode()
                finally:
                    yield b"data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        else:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                stream=False,
            )
            return JSONResponse(content=response.model_dump())

    except AuthenticationError as exc:
        LOGGER.error("Authentication failed in /v1/chat/completions request_id=%s: %s", request_id, exc)
        return JSONResponse(
            content={
                "error": {
                    "message": "Authentication failed for provider backend. Check OPENROUTER_API_KEY/OPENAI_API_KEY.",
                    "type": "authentication_error",
                    "details": str(exc),
                    "request_id": request_id,
                }
            },
            status_code=401,
        )
    except APIStatusError as exc:
        LOGGER.error("Upstream API error in /v1/chat/completions request_id=%s: %s", request_id, exc)
        return JSONResponse(
            content={
                "error": {
                    "message": f"Upstream API error: {exc}",
                    "type": "api_error",
                    "request_id": request_id,
                }
            },
            status_code=getattr(exc, "status_code", 502) or 502,
        )
    except Exception as exc:
        LOGGER.exception("Error in /v1/chat/completions request_id=%s: %s", request_id, exc)
        return JSONResponse(
            content={
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "request_id": request_id,
                }
            },
            status_code=500,
        )


if __name__ == "__main__":
    uvicorn.run(
        "standalone_server:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
    )
