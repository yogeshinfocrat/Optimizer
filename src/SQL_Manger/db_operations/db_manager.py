from src.Utils.config import GlobalConfig
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DBAPIError
import pandas as pd
from urllib.parse import quote_plus
import pyodbc
from src.Utils.log import logger
from contextlib import contextmanager
import time
from functools import wraps
import threading
import uuid


# Load the configuration from the .env file
GlobalConfig.load_config()

# Access the configuration values
SERVER = GlobalConfig.SERVER
USERNAME = GlobalConfig.DB_USER
PASSWORD = GlobalConfig.PASSWORD
DATABASE = GlobalConfig.DATABASE
PASSWORD = quote_plus(PASSWORD)

# Global engine - created once and shared (thread-safe pool)
engine = None
engine_lock = threading.Lock()  # Lock for engine initialization

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds
BACKOFF_MULTIPLIER = 2


def retry_on_db_error(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY):
    """
    Decorator to retry database operations on transient failures.
    Handles table locks, deadlocks, connection issues, and timeouts.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DBAPIError, pyodbc.Error) as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Check if it's a retryable error
                    retryable_errors = [
                        'lock', 'deadlock', 'timeout', 'connection',
                        'transport-level error', 'communication link failure',
                        'broken pipe', 'reset by peer', 'pool',
                        'transaction (process id', 'was deadlocked'
                    ]

                    is_retryable = any(err in error_msg for err in retryable_errors)

                    if not is_retryable or attempt == max_retries - 1:
                        logger.error(f"❌ {func.__name__} failed after {attempt + 1} attempts: {e}")
                        raise

                    logger.warning(
                        f"⚠️ {func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"❌ {func.__name__} failed with non-retryable error: {e}")
                    raise

            # Should never reach here, but just in case
            raise last_exception

        return wrapper

    return decorator


def build_connetion():
    """Initialize the global engine with connection pooling"""
    global engine
    with engine_lock:
        try:
            engine = create_engine(
                f'mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes',
                isolation_level="AUTOCOMMIT",
                pool_size=10,  # Number of connections to keep in pool
                max_overflow=20,  # Additional connections if pool is exhausted
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
                connect_args={
                    'timeout': 30,  # Connection timeout
                    'connect_timeout': 30
                }
            )
            logger.info("✅ Successfully connected to database")
        except Exception as e:
            logger.error(f'❌ Database connection error: {e}')
            raise


def build_separate_db_connection(conn_string, company_key):
    """
    Build a separate engine for a different database.
    WARNING: This should ONLY be called from the main thread BEFORE spawning worker threads.
    """
    global engine
    with engine_lock:
        logger.info(f'🔌 Connecting to: {company_key}')

        SERVER = conn_string.split(';')[0].split('=')[1].split(':')[1]
        DATABASE = conn_string.split(';')[1].split('=')[1]
        USERNAME = conn_string.split(';')[3].split('=')[1]
        PASSWORD = conn_string.split(';')[4].split('=')[1]
        PASSWORD = quote_plus(PASSWORD)

        try:
            engine = create_engine(
                f'mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes',
                isolation_level="AUTOCOMMIT",
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    'timeout': 30,
                    'connect_timeout': 30
                }
            )
            logger.info(f"✅ Successfully connected to {company_key}")
        except Exception as e:
            logger.error(f'❌ Connection error for {company_key}: {e}')
            raise


@contextmanager
def get_connection():
    """
    Context manager to get a thread-safe connection from the pool.
    Each thread gets its own connection from the shared pool.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    if engine is None:
        raise RuntimeError("Engine not initialized. Call build_connetion() first.")

    # This is thread-safe: each call gets a separate connection from the pool
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def close_connetion():
    """Dispose of the engine and close all connections"""
    global engine
    with engine_lock:
        if engine:
            engine.dispose()
            logger.info('🔒 Connection pool closed')
        engine = None


@retry_on_db_error(max_retries=MAX_RETRIES)
def set_status(sql_query):
    """Execute a SQL command without returning results"""
    logger.info(f"📝 Executing: {sql_query}... (Thread: {threading.current_thread().name})")
    try:
        with get_connection() as conn:
            conn.execute(text(sql_query))
        logger.info("✅ Command executed successfully")
    except Exception as e:
        logger.error(f'❌ Error executing command: {e}')
        raise
    return None


@retry_on_db_error(max_retries=MAX_RETRIES)
def fetch_data_from_db(sql_query):
    """Fetch data from database and return as DataFrame"""
    logger.info(f"🔍 Fetching data: {sql_query}... (Thread: {threading.current_thread().name})")
    try:
        with get_connection() as conn:
            result = conn.execute(text(sql_query))
            rows = result.fetchall()
            df = pd.DataFrame(rows)
            logger.info(f"✅ Fetched {len(df)} rows")
            return df
    except Exception as e:
        logger.error(f'❌ Error fetching data: {e}')
        raise




def fetch_parent_ids(table, column, values):
    """
    Fetch parent IDs dynamically using IN or = based on value count.
    """
    unique_values = tuple(set(values))

    if not unique_values:
        return []

    if len(unique_values) == 1:
        query = f"""
            SELECT {column}
            FROM {table}
            WHERE {column} = {unique_values[0]}
        """
    else:
        query = f"""
            SELECT {column}
            FROM {table}
            WHERE {column} IN {unique_values}
        """

    return fetch_data_from_db(query)


@retry_on_db_error(max_retries=MAX_RETRIES)
def insert_into_db(df, table_name, batch_size=25000, is_temp_insertion=False):
    if df.empty:
        logger.info(
            f"📥 Empty dataframe of {table_name}:")
        return None
    try:
        logger.info("Checking if all rows exist in parent table or not")

        if table_name == 'ServiceCore.CommunicationPreferencesServiceReportNotification':

            parent_ids = fetch_parent_ids(
                table='ServiceCore.WorkOrderAutoGeneration',
                column='WorkOrderAutoGenerationId',
                values=df['EntityId'].unique().tolist()
            )

            df = df[df['EntityId'].isin(parent_ids['WorkOrderAutoGenerationId'])]

        elif table_name == 'CRM.LeadNote':
            if is_temp_insertion:
                parent_ids = fetch_parent_ids(
                    table='ServiceCore.WorkOrderAutoGeneration',
                    column='WorkOrderAutoGenerationId',
                    values=df['RefId'].unique().tolist()
                )
                df = df[df['RefId'].isin(parent_ids['WorkOrderAutoGenerationId'])]

        elif table_name in [
            'ServiceCore.WorkOrderAutoGenerationServices',
            'ServiceCore.SetupAutoGenerationSourceMapping',
            'ServiceCore.WorkOrderAutoGenerationAppliedDiscount',
            'ServiceCore.SubWorkOrderAutoGeneration',
            'ServiceCore.WorkOrderAutoGenerationCommissionAdjustment',
            'ServiceCore.WorkOrderAutoGenerationSalesPersonCommission',
            'ServiceCore.WorkOrderAutoGenerationCrews'
        ]:

            parent_ids = fetch_parent_ids(
                table='ServiceCore.WorkOrderAutoGeneration',
                column='WorkOrderAutoGenerationId',
                values=df['WorkOrderAutoGenerationId'].unique().tolist()
            )

            df = df[df['WorkOrderAutoGenerationId'].isin(parent_ids['WorkOrderAutoGenerationId'])]

    except Exception as e:
        logger.error(f"Parent validation failed for {table_name}: {e}")

    """Insert DataFrame into database table with type conversion in batches"""
    logger.info(
        f"📥 Inserting into {table_name}: {df.shape[0]} rows in batches of {batch_size} (Thread: {threading.current_thread().name})")

    try:
        with get_connection() as conn:
            # Fetch column data types once
            column_data_type = pd.DataFrame()
            result = conn.execute(text(f"""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{table_name.split('.')[1]}';
            """))
            rows = result.fetchall()
            column_data_type = pd.DataFrame(rows)

            # Convert column types once for the entire dataframe
            # Ensure dataframe is independent
            df = df.copy()

            # Convert column types once for the entire dataframe
            for column_name in df.columns:
                try:
                    if column_name in column_data_type['COLUMN_NAME'].values:

                        data_type = (
                            column_data_type.loc[
                                column_data_type['COLUMN_NAME'] == column_name,
                                'DATA_TYPE'
                            ].iloc[0]
                        )

                        if data_type == 'bigint':

                            df[column_name] = (
                                pd.to_numeric(
                                    df[column_name],
                                    errors='coerce'
                                )
                                .astype('Int64')
                            )

                        elif data_type == 'varchar':

                            df[column_name] = (
                                df[column_name]
                                .astype('string')
                            )

                        elif data_type == 'bit':

                            df[column_name] = (
                                df[column_name]
                                .astype('boolean')
                            )

                except Exception:

                    try:
                        df.loc[:, column_name] = (
                            df[column_name]
                            .astype(pd.Int64Dtype())
                        )

                    except Exception as e:
                        logger.warning(
                            f'⚠️ Column type conversion warning for {column_name}: {e}'
                        )

                    continue
            # Insert data in batches
            total_rows = len(df)
            num_batches = (total_rows + batch_size - 1) // batch_size  # Ceiling division

            for batch_num in range(num_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, total_rows)
                batch_df = df.iloc[start_idx:end_idx]

                logger.info(
                    f"📤 Inserting batch {batch_num + 1}/{num_batches} ({start_idx} to {end_idx}) into {table_name}")

                batch_df.to_sql(
                    name=table_name.split('.')[1],
                    con=conn,
                    schema=table_name.split('.')[0],
                    if_exists='append',
                    index=False
                )

            logger.info(f"✅ All {total_rows} rows inserted successfully into {table_name} in {num_batches} batches")

    except Exception as e:
        logger.error(f'❌ Error in insertion: {e}')
        raise


