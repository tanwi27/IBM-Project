import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import router as api_router
from app.db.session import engine, Base, SessionLocal
from app.db.models import Resume, Score, BulletLibrary, BulletRewrite
from app.services.seed import seed_bullet_library

# Setup logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# Auto create tables on startup
logger.info("Initializing database schemas...")
Base.metadata.create_all(bind=engine)

# Auto seed bullet library database
logger.info("Pre-seeding vector reference bullet library...")
db = SessionLocal()
try:
    seed_bullet_library(db)
finally:
    db.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include main router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"message": "AI Resume Screener backend service is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
