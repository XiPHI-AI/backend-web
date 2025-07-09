from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging

load_dotenv()  # Load .env file if present

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # PostgreSQL Settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "pg-xiphi-dev-01.postgres.database.azure.com"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str

    # Neo4j Settings
    NEO4J_URI: str = "neo4j:// 20.42.92.97:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "vA6TEyAUf82J2Wi"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

logger.info("Loaded database settings:")
logger.info(f"Postgres Host: {settings.POSTGRES_HOST}")
logger.info(f"Postgres DB: {settings.POSTGRES_DB}")
logger.info(f"Neo4j URI: {settings.NEO4J_URI}")
logger.info(f"Neo4j User: {settings.NEO4J_USER}")
logger.info("Neo4j Password: [REDACTED]")