import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from config import DB_NAME


def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT
            )
        """)

        # Migration douce depuis la toute première version du bot.
        user_columns = _columns(conn, "users")
        if "last_seen_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_seen_at TEXT")
        conn.execute("UPDATE users SET last_seen_at = COALESCE(last_seen_at, created_at, ?) WHERE last_seen_at IS NULL", (datetime.now(timezone.utc).isoformat(),))

        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                cost REAL NOT NULL,
                selling_price REAL NOT NULL,
                orders INTEGER NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 0,
                profit REAL NOT NULL,
                margin REAL NOT NULL,
                score INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                product_id TEXT,
                url TEXT,
                image_url TEXT,
                commission REAL NOT NULL DEFAULT 0,
                signal_level TEXT,
                reasons TEXT,
                warnings TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        product_columns = _columns(conn, "products")
        migrations = {
            "product_id": "TEXT",
            "url": "TEXT",
            "image_url": "TEXT",
            "commission": "REAL NOT NULL DEFAULT 0",
            "signal_level": "TEXT",
            "reasons": "TEXT",
            "warnings": "TEXT",
            "shipping_cost": "REAL",
            "shipping_free": "INTEGER",
            "delivery_estimate": "TEXT",
            "net_profit": "REAL",
            "roi": "REAL",
            "net_margin": "REAL",
        }
        for column, definition in migrations.items():
            if column not in product_columns:
                conn.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        conn.commit()

        # Hunter AI tables are initialized alongside the existing Dropship database.
        conn.execute("""CREATE TABLE IF NOT EXISTS prospects (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, platform TEXT NOT NULL, contact TEXT, niche TEXT, need TEXT, status TEXT NOT NULL DEFAULT 'new', score INTEGER NOT NULL DEFAULT 0, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        prospect_columns = _columns(conn, "prospects")
        prospect_migrations = {
            "website": "TEXT",
            "address": "TEXT",
            "phone": "TEXT",
            "source": "TEXT NOT NULL DEFAULT 'manual'",
            "external_id": "TEXT",
            "rating": "REAL",
            "review_count": "INTEGER",
            "maps_url": "TEXT",
        }
        for column, definition in prospect_migrations.items():
            if column not in prospect_columns:
                conn.execute(f"ALTER TABLE prospects ADD COLUMN {column} {definition}")
        conn.execute("""CREATE TABLE IF NOT EXISTS hunter_settings (user_id INTEGER PRIMARY KEY, offer TEXT NOT NULL DEFAULT '', target TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.commit()


def get_settings(user_id):
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT key, value FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}


def set_setting(user_id, key, value):
    with closing(get_connection()) as conn:
        conn.execute(
            """INSERT INTO user_settings (user_id, key, value)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value""",
            (user_id, key, value),
        )
        conn.commit()


def add_user(user_id, username, first_name):
    now = datetime.now(timezone.utc).isoformat()
    with closing(get_connection()) as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_seen_at=excluded.last_seen_at
        """, (user_id, username, first_name, now, now))
        conn.commit()


def save_product(user_id, result, source="manual"):
    now = datetime.now(timezone.utc).isoformat()
    with closing(get_connection()) as conn:
        product_id = str(result.get("product_id", "") or "")
        if product_id:
            existing = conn.execute(
                "SELECT id FROM products WHERE user_id = ? AND product_id = ? ORDER BY id DESC LIMIT 1",
                (user_id, product_id),
            ).fetchone()
            if existing:
                return existing["id"]
        cur = conn.execute("""
            INSERT INTO products (
                user_id, name, cost, selling_price, orders, rating,
                profit, margin, score, verdict, source, product_id, url,
                image_url, commission, signal_level, reasons, warnings,
                shipping_cost, shipping_free, delivery_estimate, net_profit, roi, net_margin, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, result["name"], result["cost"], result["selling_price"],
            result.get("orders", 0), result.get("rating", 0), result["profit"],
            result["margin"], result["score"], result["verdict"], source,
            result.get("product_id", ""), result.get("url", ""),
            result.get("image_url", ""), result.get("commission", 0),
            result.get("signal_level", ""), " | ".join(result.get("reasons", [])),
            " | ".join(result.get("warnings", [])),
            result.get("shipping_cost"),
            1 if result.get("shipping_free") is True else (0 if result.get("shipping_free") is False else None),
            result.get("delivery_estimate", ""), result.get("net_profit"), result.get("roi"), result.get("net_margin"), now
        ))
        conn.commit()
        return cur.lastrowid


def get_products(user_id, limit=10):
    with closing(get_connection()) as conn:
        rows = conn.execute("""
            SELECT * FROM products
            WHERE user_id = ?
            ORDER BY score DESC, id DESC
            LIMIT ?
        """, (user_id, int(limit))).fetchall()
        return [dict(row) for row in rows]


def get_stats(user_id):
    with closing(get_connection()) as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS products,
                COALESCE(AVG(score), 0) AS avg_score,
                COALESCE(SUM(CASE WHEN verdict = '🟢 À TESTER' THEN 1 ELSE 0 END), 0) AS testable,
                COALESCE(SUM(profit), 0) AS potential_profit,
                COALESCE(SUM(net_profit), 0) AS net_profit
            FROM products
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        return dict(row)
