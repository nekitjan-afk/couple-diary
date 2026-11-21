import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "couple.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER,
                name TEXT,
                username TEXT,
                photo_url TEXT,
                link_code TEXT UNIQUE,
                created_at TEXT
            )
        """)
        
        # Добавляем колонки, если их нет (для старых баз)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN username TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN photo_url TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN link_code TEXT")
        except:
            pass
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                partner_id INTEGER,
                title TEXT,
                date TEXT,
                description TEXT,
                created_at TEXT
            )
        """)
        
        await db.commit()

async def get_or_create_user(user_id: int, name: str = None, username: str = None, photo_url: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row
        
        # Создаём нового пользователя с кодом
        code = str(user_id)[-6:].zfill(6)
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO users (user_id, name, username, photo_url, link_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, username, photo_url, code, now))
        await db.commit()
        return (user_id, None, name, username, photo_url, code, now)

async def get_user_by_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, name, username, photo_url FROM users WHERE link_code = ?", (code,)) as cursor:
            return await cursor.fetchone()

async def link_partners(user_id: int, partner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, что у обоих нет партнёра
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as c:
            if (await c.fetchone() or [None])[0]:
                return False, "У тебя уже есть партнёр"
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (partner_id,)) as c:
            if (await c.fetchone() or [None])[0]:
                return False, "У этого пользователя уже есть партнёр"
        
        await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))
        await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (user_id, partner_id))
        await db.commit()
        return True, "Успешно"

async def get_partner_info(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT u2.user_id, u2.name, u2.username, u2.photo_url
            FROM users u1
            JOIN users u2 ON u1.partner_id = u2.user_id
            WHERE u1.user_id = ?
        """, (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_event(user_id: int, title: str, date: str, description: str = ""):
    partner = await get_partner_info(user_id)
    partner_id = partner[0] if partner else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO events (user_id, partner_id, title, date, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, partner_id, title, date, description, datetime.now().isoformat()))
        await db.commit()
    return True

async def get_events(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT title, date, description FROM events
            WHERE user_id = ? OR partner_id = ?
            ORDER BY date
        """, (user_id, user_id)) as cursor:
            return await cursor.fetchall()
