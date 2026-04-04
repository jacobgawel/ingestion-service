import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.clients import close_all, initialize_all
from shared.core.logger import configure_uvicorn_logging, get_logger
from shared.core.settings import config

from api.routes import ingestion, jobs, jobs_ws

logger = get_logger("Lifespan")


@asynccontextmanager
async def lifespan(app_client: FastAPI):
    # Startup
    await initialize_all()
    logger.info("All clients initialized.")

    yield

    # Shutdown
    logger.info("Shutting down clients...")
    await close_all()
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(jobs.router)
app.include_router(jobs_ws.router)


if __name__ == "__main__":
    try:
        uvicorn.run(
            app="api.main:app",
            host=config.HOST,
            port=config.PORT,
            reload=True,
            log_level=config.APP_LOG_LEVEL,
            log_config=configure_uvicorn_logging(),
        )
    except KeyboardInterrupt, asyncio.CancelledError:
        print("Shutting down")
