from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.tasks import router as tasks_router
from backend.api.uploads import router as uploads_router
from backend.config import settings
from backend.telegram.client_manager import client_manager
from backend.tasks.task_manager import task_manager
from backend.version import APP_VERSION


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await task_manager.shutdown()
    await client_manager.shutdown()


app = FastAPI(title="纸翼 Backend", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(tasks_router)
app.include_router(uploads_router)


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
