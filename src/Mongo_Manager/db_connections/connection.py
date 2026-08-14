import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from mongoengine import connect, disconnect
from pymongo import MongoClient
from typing import Any
from src.Utils.config import GlobalConfig
from src.Utils.log import logger


class DatabaseConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_connection()
        return cls._instance

    def _init_connection(self):
        """Initialize the database connection"""
        self.connection_pool = None
        try:
            # Create a connection pool
            self.connection_pool = MongoClient(
                f"{GlobalConfig.MONGO_URI}?retryWrites=true&w=majority&appName=Cluster0",
                maxPoolSize=32,  # Match your ProcessPoolExecutor size
                maxIdleTimeMS=120000,  # 2 minutes idle time
                connectTimeoutMS=30000,  # 30 seconds connection timeout
                socketTimeoutMS=30000  # 30 seconds socket timeout
            )

            # Verify connection
            self.connection_pool.admin.command('ping')
            logger.info(
                "MongoDB Connection Pool Initialized Successfully!")
        except Exception as e:
            logger.info(f"Failed to initialize MongoDB connection pool: {e}")
            raise

    @contextmanager
    def connect_to_db(self):
        """
        Context manager to get a database connection
        Ensures proper connection management across processes
        """
        try:
            # Use mongoengine connect with the existing pool
            connect(
                db=GlobalConfig.MONGO_DB,
                host=GlobalConfig.MONGO_URI,
                maxIdleTimeMS=120000
            )
            yield self.connection_pool
        except Exception as e:
            logger.info(f"Database connection error: {e}")
            raise

    def close_connection(self):
        """Close the connection pool"""
        if self.connection_pool:
            self.connection_pool.close()
            logger.info("MongoDB Connection Pool Closed")


# Global connection manager
db_connection_manager = DatabaseConnectionManager()


# Application shutdown hook (add this to your FastAPI app)
def cleanup_db_connections():
    """
    Cleanup method to close database connections
    Call this during application shutdown
    """
    db_connection_manager.close_connection()