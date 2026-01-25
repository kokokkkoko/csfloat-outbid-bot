"""
Database migration script
Adds missing columns to existing database
"""
import asyncio
import sqlite3
from pathlib import Path


def migrate():
    """Add missing columns to existing database"""
    db_path = Path("bot.db")

    if not db_path.exists():
        print("Database not found. It will be created on first run.")
        return

    print("Migrating database...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if user_id column exists in accounts table
    cursor.execute("PRAGMA table_info(accounts)")
    columns = [col[1] for col in cursor.fetchall()]

    migrations_applied = 0

    # Add user_id column if missing
    if 'user_id' not in columns:
        print("  Adding user_id column to accounts table...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN user_id INTEGER")
        migrations_applied += 1

    # Create users table if not exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='users'
    """)
    if not cursor.fetchone():
        print("  Creating users table...")
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                is_admin BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        """)
        migrations_applied += 1

    # Add icon_url column to buy_orders table if missing
    cursor.execute("PRAGMA table_info(buy_orders)")
    buy_order_columns = [col[1] for col in cursor.fetchall()]

    if 'icon_url' not in buy_order_columns:
        print("  Adding icon_url column to buy_orders table...")
        cursor.execute("ALTER TABLE buy_orders ADD COLUMN icon_url VARCHAR(500)")
        migrations_applied += 1

    conn.commit()
    conn.close()

    if migrations_applied > 0:
        print(f"Migration complete! Applied {migrations_applied} changes.")
    else:
        print("Database is already up to date.")


if __name__ == "__main__":
    migrate()
