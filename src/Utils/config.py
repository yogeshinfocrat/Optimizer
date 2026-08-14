import os
from dotenv import load_dotenv

class GlobalConfig:
    """Global configuration variables"""

    SERVER: str = ""
    USERNAME: str = ""
    PASSWORD: str = ""
    DATABASE: str = ""
    SECURITY_KEY: str = ""
    DB_USER: str = ""


    @staticmethod
    def load_config() -> None:
        """Load the environment variables from the .env file"""
        load_dotenv()
        GlobalConfig.SERVER = os.getenv("SERVER", "")
        GlobalConfig.USERNAME = os.getenv("USER", "")
        GlobalConfig.PASSWORD = os.getenv("PASSWORD", "")
        GlobalConfig.DATABASE = os.getenv("DATABASE", "")
        GlobalConfig.SECURITY_KEY = os.getenv("SECURITY_KEY","")
        GlobalConfig.DB_USER = os.getenv("DB_USER")
        ####--------------------------------------------------
        GlobalConfig.MONGO_DB = os.getenv("MONGO_DB")
        GlobalConfig.MONGO_URI = os.getenv("MONGO_URI")
        GlobalConfig.ENVIRONMENT = os.getenv("ENVIRONMENT") or "development"  # type: ignore
        GlobalConfig.SENTRY_DSN = os.getenv("SENTRY_DSN")
        GlobalConfig.LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"  # type: ignore
        debug_flag_str = os.getenv("DEBUG_FLAG", "False")
        GlobalConfig.DEBUG_FLAG = debug_flag_str.lower() in ("true", "1", "t")
        # Load and convert TEST_KEYS
        test_keys_str = os.getenv("TEST_KEYS", "")
        GlobalConfig.TEST_KEYS = [key.strip() for key in test_keys_str.split(',') if key.strip()]
        universal_key = os.getenv("UNIVERSAL_KEY", False)
        GlobalConfig.UNIVERSAL_KEY = universal_key
        GlobalConfig.COMPLETION_API = os.getenv('COMPLETION_API')