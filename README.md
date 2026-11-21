# Couple Dairy — Telegram Mini App для пар

Приложение внутри Telegram с общим календарём и воспоминаниями.

## Что умеет сейчас
- Общий календарь (события видны обоим)
- Раздел «Воспоминания» (название, дата, место)
- Красивый интерфейс Mini App

## Как запустить

### 1. Создай бота
Напиши [@BotFather](https://t.me/BotFather) → `/newbot` → получи токен.

### 2. Установи зависимости
```bash
cd couple-app
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настрой .env
Скопируй `.env.example` в `.env` и вставь свой токен:
```
BOT_TOKEN=123456:ABC-DEF...
WEBAPP_URL=http://localhost:8080
```

### 4. Запусти
```bash
python bot.py
```

### 5. Открой бота в Telegram
Напиши `/start` — появится кнопка «Открыть приложение».

## Важно про Mini App
Для полноценной работы Mini App нужен **HTTPS**.  
Локально можно тестировать через:
- [ngrok](https://ngrok.com/) (`ngrok http 8080`)
- или [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)

После получения публичного HTTPS-адреса впиши его в `WEBAPP_URL` в файле `.env`.

## Что дальше
- Доделать систему связки пар (сейчас упрощённо)
- Реализовать загрузку фото в воспоминания
- Добавить уведомления
- Улучшить дизайн

## Структура
- `bot.py` — бот + веб-сервер
- `database.py` — база данных (SQLite)
- `webapp/index.html` — интерфейс Mini App
