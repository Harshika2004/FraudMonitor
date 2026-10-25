import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Engine configuration with connection pooling
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "echo": False,
}

# In SQLite mode (used for tests or fallback), check_same_thread needs to be False
db_url = settings.get_database_url()
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

try:
    engine = create_engine(db_url, **engine_kwargs)
except Exception as e:
    logger.error(f"Failed to initialize SQLAlchemy engine: {e}")
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency that provides an isolated database session per request."""
    if engine is None:
        raise RuntimeError("Database engine is not configured. Check your .env configuration.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
