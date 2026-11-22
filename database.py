import asyncpg
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL)

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                partner_id BIGINT,
                name TEXT,
                username TEXT,
                photo_url TEXT,
                link_code TEXT UNIQUE,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                partner_id BIGINT,
                title TEXT,
                date TEXT,
                description TEXT,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                event_title TEXT,
                event_date TEXT,
                remind_at TEXT,
                user_id BIGINT,
                partner_id BIGINT,
                target TEXT,
                custom_text TEXT,
                sent INTEGER DEFAULT 0
            )
        """)

async def get_or_create_user(user_id: int, name: str = None, username: str = None, photo_url: str = None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if row:
            return row
        code = str(user_id)[-6:].zfill(6)
        now = datetime.now().isoformat()
        await conn.execute("""
            INSERT INTO users (user_id, name, username, photo_url, link_code, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, name, username, photo_url, code, now)
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def get_user_by_code(code: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT user_id, name, username, photo_url FROM users WHERE link_code = $1", code)

async def link_partners(user_id: int, partner_id: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
        await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", partner_id)
        
        row = await conn.fetchrow("SELECT partner_id FROM users WHERE user_id = $1", user_id)
        if row and row["partner_id"]:
            return False, "У тебя уже есть партнёр"
        row = await conn.fetchrow("SELECT partner_id FROM users WHERE user_id = $1", partner_id)
        if row and row["partner_id"]:
            return False, "У этого пользователя уже есть партнёр"
        
        await conn.execute("UPDATE users SET partner_id = $1 WHERE user_id = $2", partner_id, user_id)
        await conn.execute("UPDATE users SET partner_id = $1 WHERE user_id = $2", user_id, partner_id)
        return True, "Успешно"

async def unlink_partners(user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT partner_id FROM users WHERE user_id = $1", user_id)
        if not row or not row["partner_id"]:
            return False, "Партнёр не привязан"
        partner_id = row["partner_id"]
        await conn.execute("UPDATE users SET partner_id = NULL WHERE user_id = $1", user_id)
        await conn.execute("UPDATE users SET partner_id = NULL WHERE user_id = $1", partner_id)
        return True, "Отвязано"

async def get_partner_info(user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT partner_id FROM users WHERE user_id = $1", user_id)
        if not row or not row["partner_id"]:
            return None
        return await conn.fetchrow("SELECT user_id, name, username, photo_url FROM users WHERE user_id = $1", row["partner_id"])

async def add_event(user_id: int, title: str, date: str, description: str = ""):
    partner = await get_partner_info(user_id)
    partner_id = partner["user_id"] if partner else None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO events (user_id, partner_id, title, date, description, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, user_id, partner_id, title, date, description, datetime.now().isoformat())
    return True

async def get_events(user_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT title, date, description FROM events
            WHERE user_id = $1 OR partner_id = $1
            ORDER BY date
        """, user_id)
        return [(r["title"], r["date"], r["description"]) for r in rows]

async def add_reminder(event_title: str, event_date: str, remind_at: str, user_id: int, partner_id, target: str, text: str = ""):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO reminders (event_title, event_date, remind_at, user_id, partner_id, target, custom_text)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, event_title, event_date, remind_at, user_id, partner_id, target, text)
    return True

async def get_due_reminders():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, event_title, user_id, partner_id, target, custom_text, remind_at
            FROM reminders WHERE sent = 0
        """)
        due = []
        for r in rows:
            remind_at = (r["remind_at"] or "")[:16].replace(" ", "T")
            if remind_at and remind_at <= now:
                due.append((r["id"], r["event_title"], r["user_id"], r["partner_id"], r["target"], r["custom_text"]))
        return due

async def mark_reminder_sent(reminder_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE reminders SET sent = 1 WHERE id = $1", reminder_id)
