import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "couple.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Пользователи и связь пар
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER,
                name TEXT,
                created_at TEXT
            )
        """)
        
        # События календаря
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
        
        # Воспоминания
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                partner_id INTEGER,
                title TEXT,
                date TEXT,
                place TEXT,
                photos TEXT,  -- JSON список file_id
                created_at TEXT
            )
        """)
        
        await db.commit()

async def get_partner(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def link_partners(user1: int, user2: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, partner_id, created_at)
            VALUES (?, ?, ?)
        """, (user1, user2, now))
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, partner_id, created_at)
            VALUES (?, ?, ?)
        """, (user2, user1, now))
        await db.commit()

# === Календарь ===
async def add_event(user_id: int, title: str, date: str, description: str = ""):
    partner = await get_partner(user_id)
    if not partner:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO events (user_id, partner_id, title, date, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, partner, title, date, description, datetime.now().isoformat()))
        await db.commit()
    return True

async def get_events(user_id: int):
    partner = await get_partner(user_id)
    if not partner:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT title, date, description FROM events
            WHERE user_id = ? OR partner_id = ?
            ORDER BY date
        """, (user_id, user_id)) as cursor:
            return await cursor.fetchall()

# === Воспоминания ===
async def add_memory(user_id: int, title: str, date: str, place: str, photos: list):
    partner = await get_partner(user_id)
    if not partner:
        return False
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO memories (user_id, partner_id, title, date, place, photos, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, partner, title, date, place, json.dumps(photos), datetime.now().isoformat()))
        await db.commit()
    return True

async def get_memories(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT title, date, place, photos FROM memories
            WHERE user_id = ? OR partner_id = ?
            ORDER BY date DESC
        """, (user_id, user_id)) as cursor:
            rows = await cursor.fetchall()
            import json
            return [
                {
                    "title": r[0],
                    "date": r[1],
                    "place": r[2],
                    "photos": json.loads(r[3]) if r[3] else []
                } for r in rows
            ]
