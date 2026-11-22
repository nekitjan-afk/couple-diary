import os
import asyncio
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "Добро пожаловать в Couple Dairy!\n\n"
        "Это ваше общее приложение — календарь.\n"
        "Нажми кнопку ниже.",
        reply_markup=kb
    )

# ========== WEB SERVER ==========
async def handle_index(request):
    return web.FileResponse("index.html")

async def api_me(request):
    user_id = int(request.query.get("user_id", 0))
    name = request.query.get("name")
    username = request.query.get("username")
    photo = request.query.get("photo")
    
    await db.get_or_create_user(user_id, name, username, photo)
    partner = await db.get_partner_info(user_id)
    
    return web.json_response({
        "user_id": user_id,
        "partner": {
            "id": partner[0],
            "name": partner[1],
            "username": partner[2],
            "photo": partner[3]
        } if partner else None
    })

async def api_link(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        code = str(data.get("code", "")).strip()
        
        if not code:
            return web.json_response({"ok": False, "error": "Введи код"})
        
        partner_row = await db.get_user_by_code(code)
        if not partner_row:
            return web.json_response({"ok": False, "error": "Код не найден"})
        
        partner_id = partner_row[0]
        if partner_id == user_id:
            return web.json_response({"ok": False, "error": "Нельзя привязать себя"})
        
        success, msg = await db.link_partners(user_id, partner_id)
        if not success:
            return web.json_response({"ok": False, "error": msg})
        
        return web.json_response({
            "ok": True,
            "partner": {
                "id": partner_id,
                "name": partner_row[1],
                "username": partner_row[2],
                "photo": partner_row[3]
            }
        })
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Сервер: {str(e)}"})

async def api_unlink(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        success, msg = await db.unlink_partners(user_id)
        return web.json_response({"ok": success, "message": msg})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def api_add_event(request):
    data = await request.json()
    user_id = data.get("user_id")
    title = data.get("title")
    date = data.get("date")
    description = data.get("description", "")
    await db.add_event(user_id, title, date, description)
    return web.json_response({"ok": True})

async def api_get_events(request):
    user_id = int(request.query.get("user_id", 0))
    events = await db.get_events(user_id)
    return web.json_response([
        {"title": e[0], "date": e[1], "description": e[2]} for e in events
    ])

async def api_add_reminder(request):
    try:
        data = await request.json()
        await db.add_reminder(
            data.get("title"),
            data.get("event_date"),
            data.get("remind_at"),
            data.get("user_id"),
            data.get("partner_id"),
            data.get("target")
        )
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def check_reminders():
    while True:
        try:
            reminders = await db.get_due_reminders()
            for r in reminders:
                rid, title, uid, pid, target = r
                text = f"Не забудьте о вашем событии:\n\n<b>{title}</b>"
                if target in ("me", "both") and uid:
                    await bot.send_message(uid, text, parse_mode="HTML")
                if target in ("partner", "both") and pid:
                    await bot.send_message(pid, text, parse_mode="HTML")
                await db.mark_reminder_sent(rid)
        except Exception as e:
            print("Reminder error:", e)
        await asyncio.sleep(30)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/link", api_link)
    app.router.add_post("/api/unlink", api_unlink)
    app.router.add_post("/api/event", api_add_event)
    app.router.add_post("/api/reminder", api_add_reminder)
    app.router.add_get("/api/events", api_get_events)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    await db.init_db()
    await start_web_server()
    asyncio.create_task(check_reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
