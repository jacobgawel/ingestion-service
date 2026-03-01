import asyncio
from contextlib import asynccontextmanager

import torch
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.minio_client import _minio_singleton
from app.clients.nats_client import close_nats, initialize_nats
from app.clients.scylla_client import close_scylla, initialize_scylla
from app.clients.temporal_client import close_temporal, initialize_temporal
from app.core.logger import configure_uvicorn_logging, get_logger
from app.core.settings import config
from app.routes import ingestion, jobs

logger = get_logger("Lifespan")


@asynccontextmanager
async def lifespan(app_client: FastAPI):
    # Startup
    logger.info("Initializing Temporal client...")
    await initialize_temporal()

    logger.info("Initializing MinIO client...")
    _minio_singleton.initialize()

    logger.info("Initializing ScyllaDB client...")
    await initialize_scylla()

    logger.info("Initializing NATS client...")
    await initialize_nats()

    logger.info("All clients initialized.")

    yield

    # Shutdown
    logger.info("Shutting down clients...")
    await close_nats()
    await close_temporal()
    await close_scylla()
    _minio_singleton.close()
    logger.info("All clients shut down.")


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
app.include_router(jobs.router)


if __name__ == "__main__":
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
