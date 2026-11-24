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
            CREATE TABLE IF NOT EXISTS wishlist (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                partner_id BIGINT,
                title TEXT,
                cat TEXT,
                description TEXT,
                link TEXT,
                photo TEXT,
                created_at TEXT
            )
        """)
        try:
            await conn.execute("ALTER TABLE wishlist ADD COLUMN IF NOT EXISTS link TEXT")
            await conn.execute("ALTER TABLE wishlist ADD COLUMN IF NOT EXISTS photo TEXT")
        except:
            pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moods (
                user_id BIGINT PRIMARY KEY,
                mood TEXT,
                updated_at TEXT
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
        await conn.execute("DELETE FROM events WHERE user_id = $1", partner_id)
        await conn.execute("DELETE FROM wishlist WHERE user_id = $1", partner_id)
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

async def delete_event(user_id: int, title: str, date: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM events 
            WHERE (user_id = $1 OR partner_id = $1) AND title = $2 AND date = $3
        """, user_id, title, date)
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

async def add_wish(user_id: int, title: str, cat: str, description: str = "", link: str = "", photo: str = ""):
    partner = await get_partner_info(user_id)
    partner_id = partner["user_id"] if partner else None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wishlist (user_id, partner_id, title, cat, description, link, photo, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, user_id, partner_id, title, cat, description, link, photo, datetime.now().isoformat())
    return True

async def get_wishes(user_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_id, title, cat, description, link, photo FROM wishlist
            WHERE user_id = $1 OR partner_id = $1
            ORDER BY id DESC
        """, user_id)
        return [(r["user_id"], r["title"], r["cat"], r["description"], r["link"], r["photo"]) for r in rows]

async def delete_wish(user_id: int, title: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM wishlist WHERE user_id = $1 AND title = $2
        """, user_id, title)
    return True

async def set_mood(user_id: int, mood: str, date: str = None):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO moods (user_id, mood, updated_at) VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET mood = $2, updated_at = $3
        """, user_id, mood, date)

async def get_partner_mood(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT partner_id FROM users WHERE user_id = $1", user_id)
        if not row or not row["partner_id"]:
            return None
        mood_row = await conn.fetchrow("SELECT mood, updated_at FROM moods WHERE user_id = $1", row["partner_id"])
        if not mood_row or mood_row["updated_at"] != today:
            return None
        return mood_row["mood"]

async def cleanup_old_events():
    today = datetime.now().strftime("%Y-%m-%d")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM events WHERE date < $1", today)

async def get_due_reminders():
    from datetime import datetime, timezone, timedelta
    # Сервер в UTC, пользователь в GMT+3
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(hours=3)
    now_str = now_local.strftime("%Y-%m-%dT%H:%M")
    print(f"Now local (GMT+3): {now_str}")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, event_title, user_id, partner_id, target, custom_text, remind_at
            FROM reminders WHERE sent = 0
        """)
        due = []
        for r in rows:
            remind_at = (r["remind_at"] or "")[:16].replace(" ", "T")
            print(f"Check: {remind_at} <= {now_str}")
            if remind_at and remind_at <= now_str:
                due.append((r["id"], r["event_title"], r["user_id"], r["partner_id"], r["target"], r["custom_text"]))
        return due

async def mark_reminder_sent(reminder_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE reminders SET sent = 1 WHERE id = $1", reminder_id)
