import os
import asyncio
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import database as db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== БОТ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Открыть приложение",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}")
        )]
    ])
    await message.answer(
        "Добро пожаловать в Couple Dairy!\n\n"
        "Это ваше общее приложение — календарь и воспоминания.\n"
        "Нажми кнопку ниже.",
        reply_markup=kb
    )

@dp.message(Command("mylink"))
async def cmd_mylink(message: types.Message):
    code = str(message.from_user.id)[-6:]  # последние 6 цифр как код
    await message.answer(f"Твой код для партнёра: `{code}`\n\nОтправь ему этот код.", parse_mode="Markdown")

@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /link КОД")
        return
    code = args[1]
    # Простая связка по последним 6 цифрам (для теста)
    # В реальности лучше делать через отдельную таблицу кодов
    await message.answer("Связка пока работает в тестовом режиме. Функция будет улучшена.")

# ========== WEB SERVER (API для Mini App) ==========
async def handle_index(request):
    return web.FileResponse("index.html")

async def api_add_event(request):
    data = await request.json()
    user_id = data.get("user_id")
    title = data.get("title")
    date = data.get("date")
    description = data.get("description", "")
    
    success = await db.add_event(user_id, title, date, description)
    return web.json_response({"ok": success})

async def api_get_events(request):
    user_id = int(request.query.get("user_id", 0))
    events = await db.get_events(user_id)
    return web.json_response([
        {"title": e[0], "date": e[1], "description": e[2]} for e in events
    ])

async def api_add_memory(request):
    data = await request.json()
    user_id = data.get("user_id")
    title = data.get("title")
    date = data.get("date")
    place = data.get("place")
    photos = data.get("photos", [])
    
    success = await db.add_memory(user_id, title, date, place, photos)
    return web.json_response({"ok": success})

async def api_get_memories(request):
    user_id = int(request.query.get("user_id", 0))
    memories = await db.get_memories(user_id)
    return web.json_response(memories)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    #app.router.add_static("/webapp", "webapp")
    app.router.add_post("/api/event", api_add_event)
    app.router.add_get("/api/events", api_get_events)
    app.router.add_post("/api/memory", api_add_memory)
    app.router.add_get("/api/memories", api_get_memories)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    await db.init_db()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
