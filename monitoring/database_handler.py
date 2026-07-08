import os
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB", "employee_tracker"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
}

try:
    max_connections = int(os.getenv("POSTGRES_POOL_MAX", "20"))
    connection_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=max_connections,
        **DB_CONFIG
    )
    logger.info("Database connection pool initialized.")
except Exception as e:
    logger.error("Failed to initialize database pool: %s", e)
    connection_pool = None


def run_query(query, params=None, fetch_one=False, fetch_all=False):
    if not connection_pool:
        logger.error("DB connection pool not available")
        return None

    conn = None
    cur = None

    try:
        conn = connection_pool.getconn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(query, params)

        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()

        conn.commit()
        return result

    except Exception as e:
        logger.error("DB query failed: %s", e)
        if conn:
            conn.rollback()
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            connection_pool.putconn(conn)


def close_all_connections():
    if connection_pool:
        connection_pool.closeall()
        logger.info("All DB connections closed.")



def fetch_and_lock_events(limit=50):
    sql = """
    SELECT *
    FROM monitoring_clientevent
    WHERE status = 'accepted'
    ORDER BY received_at ASC
    LIMIT %s;
    """
    return run_query(sql, (limit,), fetch_all=True)


def mark_in_progress(event_id):
    sql = """
    UPDATE monitoring_clientevent
    SET status = 'processing'
    WHERE event_id = %s;
    """
    run_query(sql, (event_id,))


def mark_synced(event_id):
    sql = """
    UPDATE monitoring_clientevent
    SET status = 'synced'
    WHERE event_id = %s;
    """
    run_query(sql, (event_id,))


def mark_dead_letter(event_id, reason):
    sql = """
    UPDATE monitoring_clientevent
    SET status = 'rejected',
        error_message = %s
    WHERE event_id = %s;
    """
    run_query(sql, (reason, event_id))


def increment_retry(event_id, reason):
    logger.warning("Retry event_id=%s reason=%s", event_id, reason)



def get_pending_screenshots(limit=20):
    sql = """
    SELECT *
    FROM monitoring_screenshot
    ORDER BY timestamp ASC
    LIMIT %s;
    """
    return run_query(sql, (limit,), fetch_all=True)


def mark_screenshot_synced(screenshot_id):
    sql = """
    DELETE FROM monitoring_screenshot
    WHERE id = %s;
    """
    run_query(sql, (screenshot_id,))


def mark_screenshot_retry(screenshot_id, reason):
    logger.warning("Screenshot retry id=%s reason=%s", screenshot_id, reason)



def create_user(full_name, email, password_hash, role='employee', is_active=True):
    sql = """
    INSERT INTO users (full_name, email, password_hash, role, is_active, created_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id;
    """
    return run_query(sql, (full_name, email, password_hash, role, is_active, datetime.now()), fetch_one=True)


def update_last_login(user_id):
    sql = """
    UPDATE users
    SET last_login = %s
    WHERE id = %s;
    """
    run_query(sql, (datetime.now(), user_id))


def get_user_by_email(email):
    sql = "SELECT * FROM users WHERE email = %s;"
    return run_query(sql, (email,), fetch_one=True)


def get_user_sessions(user_id):
    sql = """
    SELECT * FROM sessions
    WHERE user_id = %s
    ORDER BY start_time DESC;
    """
    return run_query(sql, (user_id,), fetch_all=True)


if __name__ == "__main__":
    print("Database handler is ready and aligned with Django models.")