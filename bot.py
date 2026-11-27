import os
import asyncio
import aiohttp
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

@dp.message(Command("testremind"))
async def cmd_testremind(message: types.Message):
    await message.answer("Тестовое напоминание:\n\n<b>Проверка</b>\nНе забудьте о событии", parse_mode="HTML")

async def handle_index(request):
    response = web.FileResponse("index.html")
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
            "id": partner["user_id"],
            "name": partner["name"],
            "username": partner["username"],
            "photo": partner["photo_url"]
        } if partner else None
    })

async def api_link(request):
    data = await request.json()
    user_id = data.get("user_id")
    code = data.get("code")
    partner_row = await db.get_user_by_code(code)
    if not partner_row:
        return web.json_response({"ok": False, "error": "Код не найден"})
    partner_id = partner_row["user_id"]
    ok, msg = await db.link_partners(user_id, partner_id)
    if not ok:
        return web.json_response({"ok": False, "error": msg})
    return web.json_response({
        "ok": True,
        "partner": {
            "id": partner_id,
            "name": partner_row["name"],
            "username": partner_row["username"],
            "photo": partner_row["photo_url"]
        }
    })

async def api_unlink(request):
    data = await request.json()
    user_id = data.get("user_id")
    ok, msg = await db.unlink_partners(user_id)
    return web.json_response({"ok": ok, "error": msg if not ok else None})

async def api_add_event(request):
    data = await request.json()
    await db.add_event(data.get("user_id"), data.get("title"), data.get("date"), data.get("description", ""))
    return web.json_response({"ok": True})

async def api_delete_event(request):
    data = await request.json()
    await db.delete_event(data.get("user_id"), data.get("title"), data.get("date"))
    return web.json_response({"ok": True})

async def api_set_mood(request):
    data = await request.json()
    await db.set_mood(data.get("user_id"), data.get("mood"), data.get("date"))
    return web.json_response({"ok": True})

async def api_set_wish_status(request):
    data = await request.json()
    await db.set_wish_status(data.get("user_id"), data.get("title"), data.get("status"))
    return web.json_response({"ok": True})

async def api_delete_wish(request):
    data = await request.json()
    await db.delete_wish(data.get("user_id"), data.get("title"))
    return web.json_response({"ok": True})
    data = await request.json()
    await db.delete_wish(data.get("user_id"), data.get("title"))
    return web.json_response({"ok": True})

async def api_add_wish(request):
    data = await request.json()
    await db.add_wish(data.get("user_id"), data.get("title"), data.get("cat"), data.get("description", ""), data.get("link", ""), data.get("photo", ""))
    return web.json_response({"ok": True})

async def api_get_wishes(request):
    user_id = int(request.query.get("user_id", 0))
    wishes = await db.get_wishes(user_id)
    return web.json_response([{"user_id": w[0], "title": w[1], "cat": w[2], "desc": w[3], "link": w[4], "photo": w[5], "status": w[6]} for w in wishes])

async def api_get_mood(request):
    user_id = int(request.query.get("user_id", 0))
    mood = await db.get_partner_mood(user_id)
    return web.json_response({"mood": mood})

async def api_get_events(request):
    user_id = int(request.query.get("user_id", 0))
    events = await db.get_events(user_id)
    return web.json_response([{"title": e[0], "date": e[1], "description": e[2]} for e in events])

async def api_movie_poster(request):
    title = request.query.get("title", "")
    mtype = request.query.get("type", "movie")
    if not title:
        return web.json_response({"poster": None})
    endpoint = "tv" if mtype in ("Сериал", "Аниме") else "movie"
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.themoviedb.org/3/search/{endpoint}?api_key=3fd2be6f0c70a2a598f084ddfb75487c&query={title}&language=en"
            async with session.get(url) as resp:
                data = await resp.json()
                if data.get("results") and data["results"][0].get("poster_path"):
                    poster = "https://image.tmdb.org/t/p/w500" + data["results"][0]["poster_path"]
                    return web.json_response({"poster": poster})
    except Exception as e:
        print("TMDB error:", e)
    return web.json_response({"poster": None})

async def api_date_idea(request):
    cat = request.query.get("cat", "all")
    ideas = {
        "общение": ["Ужин при свечах", "Пикник на закате", "Прогулка под звёздами"],
        "отдых": ["Кино дома с попкорном", "Настольные игры", "Спа-день дома"],
        "еда": ["Готовим вместе новый рецепт", "Дегустация десертов", "Завтрак в постель"],
        "актив": ["Прогулка на велосипедах", "Боулинг", "Каток"],
        "творчество": ["Рисуем вместе", "Готовим десерт", "Фотосессия дома"]
    }
    import random
    pool_ideas = ideas.get(cat, ideas["общение"])
    return web.json_response({"activity": random.choice(pool_ideas), "type": cat})

async def api_add_reminder(request):
    try:
        data = await request.json()
        print(">>> NEW REMINDER:", data)
        await db.add_reminder(
            data.get("title"),
            data.get("event_date"),
            data.get("remind_at"),
            int(data.get("user_id") or 0),
            data.get("partner_id"),
            data.get("target"),
            data.get("text", "")
        )
        print(">>> Reminder saved")
        return web.json_response({"ok": True})
    except Exception as e:
        print(">>> Reminder error:", e)
        return web.json_response({"ok": False, "error": str(e)})

async def check_reminders():
    print("=== Reminder checker started ===")
    while True:
        try:
            try:
                await db.cleanup_old_events()
            except:
                pass
            reminders = await db.get_due_reminders()
            print(f"Due reminders: {len(reminders)}")
            print(f"Due reminders: {len(reminders)}")
            for r in reminders:
                rid, title, uid, pid, target, custom = r
                text = f"{custom or 'Не забудьте о вашем событии'}\n\n<b>{title}</b>"
                print(f"Sending {rid} to {uid}/{pid}")
                try:
                    if target in ("me", "both") and uid:
                        await bot.send_message(int(uid), text, parse_mode="HTML")
                    if target in ("partner", "both") and pid:
                        await bot.send_message(int(pid), text, parse_mode="HTML")
                    await db.mark_reminder_sent(rid)
                    print(f"Sent {rid}")
                except Exception as e:
                    print(f"Send fail: {e}")
        except Exception as e:
            print("Checker error:", e)
        await asyncio.sleep(15)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/link", api_link)
    app.router.add_post("/api/unlink", api_unlink)
    app.router.add_post("/api/event", api_add_event)
    app.router.add_post("/api/event/delete", api_delete_event)
    app.router.add_post("/api/reminder", api_add_reminder)
    app.router.add_post("/api/wish/status", api_set_wish_status)
    app.router.add_post("/api/wish/delete", api_delete_wish)
    app.router.add_post("/api/wish", api_add_wish)
    app.router.add_get("/api/wishes", api_get_wishes)
    app.router.add_post("/api/mood", api_set_mood)
    app.router.add_get("/api/mood", api_get_mood)
    app.router.add_get("/api/poster", api_movie_poster)
    app.router.add_get("/api/date-idea", api_date_idea)
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
