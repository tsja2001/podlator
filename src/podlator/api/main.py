"""FastAPI 应用入口。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from podlator.api.log_hub import LogHub
from podlator.api.routes import router as api_router
from podlator.api.ws import router as ws_router
from podlator.config import Settings
from podlator.logging import set_log_hub
from podlator.storage.db import TaskStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """管理 TaskStore 生命周期。"""
    settings = Settings()
    # 确保数据目录存在
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    store = TaskStore(settings.database_path)
    await store.initialize()
    app.state.store = store
    app.state.settings = settings

    log_hub = LogHub()
    app.state.log_hub = log_hub
    set_log_hub(log_hub)

    yield

    set_log_hub(None)
    await store.close()


app = FastAPI(
    title="Podlator",
    description="英文播客/视频 → 中文简报自动化工具",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)
