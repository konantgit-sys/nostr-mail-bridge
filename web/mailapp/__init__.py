"""Nostr Mail — веб-клиент (пакет).

create_app(): FastAPI + роутеры + мост (lifespan) + статика + оптимизации
(GZip, Cache-Control для статики). Точка входа: app.py → create_app().
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import PUBKEY, NPUB, STATIC_DIR
from .bridge import init_bridge
from .routers import mail


class CacheControlMiddleware:
    """Статика (*.css, *.js, *.png…) — кэш 1 час; всё остальное — no-cache."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                path = scope.get("path", "")
                if path.startswith("/static/"):
                    headers.append((b"cache-control", b"public, max-age=3600"))
                else:
                    headers.append((b"cache-control", b"no-cache"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


def create_app() -> FastAPI:
    app = FastAPI(title="Nostr Mail", docs_url=None, redoc_url=None)

    # GZip НЕ включаем: внешний прокси *.v2.site сам сжимает ответы,
    # двойное сжатие обрезает поток (проверено 2026-08-26).
    app.add_middleware(CacheControlMiddleware)

    @app.on_event("startup")
    def _startup():
        init_bridge()

    # статика (кэш заголовками Cache-Control, см. middleware)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    # API-роутеры (включая NIP-05 discovery)
    app.include_router(mail.router)

    return app
