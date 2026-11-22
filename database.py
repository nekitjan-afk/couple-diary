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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_title TEXT,
                event_date TEXT,
                remind_at TEXT,
                user_id INTEGER,
                partner_id INTEGER,
                target TEXT,
                custom_text TEXT,
                sent INTEGER DEFAULT 0
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
        # Убеждаемся, что оба пользователя существуют
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (partner_id,))
        
        # Проверяем, что у обоих нет партнёра
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            if row and row[0]:
                return False, "У тебя уже есть партнёр"
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (partner_id,)) as c:
            row = await c.fetchone()
            if row and row[0]:
                return False, "У этого пользователя уже есть партнёр"
        
        # Привязываем взаимно
        await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))
        await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (user_id, partner_id))
        await db.commit()
        return True, "Успешно"

async def unlink_partners(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Находим партнёра
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            if not row or not row[0]:
                return False, "Партнёр не привязан"
            partner_id = row[0]
        
        # Отвязываем обоих
        await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (user_id,))
        await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (partner_id,))
        await db.commit()
        return True, "Отвязано"

async def get_partner_info(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            if not row or not row[0]:
                return None
            partner_id = row[0]
        async with db.execute("SELECT user_id, name, username, photo_url FROM users WHERE user_id = ?", (partner_id,)) as c:
            return await c.fetchone()

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

async def add_reminder(event_title: str, event_date: str, remind_at: str, user_id: int, partner_id: int, target: str, text: str = ""):
    print(f"DB add_reminder: title={event_title}, remind_at={remind_at}, user={user_id}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO reminders (event_title, event_date, remind_at, user_id, partner_id, target, custom_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_title, event_date, remind_at, user_id, partner_id, target, text))
        await db.commit()
    print("DB insert done")
    return True

async def get_due_reminders():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    print(f"Checking reminders, now = {now}")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, remind_at, sent FROM reminders") as cursor:
            all_r = await cursor.fetchall()
            print(f"All reminders in DB: {all_r}")
        async with db.execute("""
            SELECT id, event_title, user_id, partner_id, target, custom_text, remind_at
            FROM reminders WHERE sent = 0
        """) as cursor:
            rows = await cursor.fetchall()
            due = []
            for row in rows:
                remind_at = (row[6] or "")[:16].replace(" ", "T")
                print(f"Compare: {remind_at} <= {now} ?")
                if remind_at and remind_at <= now:
                    due.append(row[:6])
            return due

async def mark_reminder_sent(reminder_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
        await db.commit()

async def get_events(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT title, date, description FROM events
            WHERE user_id = ? OR partner_id = ?
            ORDER BY date
        """, (user_id, user_id)) as cursor:
            return await cursor.fetchall()
