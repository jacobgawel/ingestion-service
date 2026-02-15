import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import config
from app.core.logger import configure_uvicorn_logging
from app.routes import ingestion


@asynccontextmanager
async def lifespan(app_client: FastAPI):
    yield


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    debug=config.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)

if __name__ == "__main__":
    import torch

    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    print(
        f"GPU device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}"
    )

    try:
        uvicorn.run(
            app=config.ASGI_PATH,
            host=config.HOST,
            port=config.PORT,
            reload=True,
            log_level=config.APP_LOG_LEVEL,
            log_config=configure_uvicorn_logging(),
        )
    except KeyboardInterrupt, asyncio.CancelledError:
        print("Shutting down")
