from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
import requests
import logging

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

app = FastAPI(title="Валера")


class MeetingRequest(BaseModel):
    zoom_url: str


class LeaveRequest(BaseModel):
    bot_id: str


# Функция для вывода финальных предложений
def log_transcript(speaker: str, text: str):
    logger.info(f"🗣 [РЕАЛ-ТАЙМ] {speaker}: {text}")


# --- ЭНДПОИНТ 1: ЗАПУСК БОТА ---
@app.post("/api/trigger-bot")
async def trigger_bot(meeting: MeetingRequest):
    zoom_link = "https://us04web.zoom.us/j/76219252785?pwd=SkYnoSbXPrfanpR0FNCrE6FbIf2JEO.1"
    logger.info(f"👉 Подключаем бота к: {zoom_link}")

    recall_api_key = "5336b71d829b10622215e40d03cac4cecd8a315a"
    recall_url = "https://us-west-2.recall.ai/api/v1/bot"

    # Payload с принудительным включением Real-Time транскрипции
    payload = {
        "meeting_url": zoom_link,
        "bot_name": "Валера",
        "real_time_endpoints": [
            {
                "type": "webhook",
                "config": {
                    "url": "https://us-west-2.ngrok-free.app/webhook/recall",
                    "events": ["bot.status_change", "transcript.data", "participant_events.join"]
                }
            }
        ],
        # Включаем именно ПОТОКОВУЮ (Real-Time) транскрибацию
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {}
                }
            }
        }
    }

    headers = {
        "Authorization": f"Token {recall_api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(recall_url, json=payload, headers=headers)
        response.raise_for_status()

        bot_id = response.json().get("id")
        logger.info(f"✅ Успешно! ID бота: {bot_id}")
        return {"status": "success", "bot_id": bot_id}
    except Exception as e:
        logger.error(f"🚨 Ошибка при отправке в Recall: {e}")
        return {"status": "error"}


# --- ЭНДПОИНТ 2: ВЫКЛЮЧИТЬ БОТА ---
@app.post("/api/leave-bot")
async def leave_bot(leave_req: LeaveRequest):
    recall_api_key = "5336b71d829b10622215e40d03cac4cecd8a315a"
    recall_url = f"https://us-west-2.recall.ai/api/v1/bot/{leave_req.bot_id}/leave_call/"

    headers = {
        "Authorization": f"Token {recall_api_key}",
        "Content-Type": "application/json"
    }

    try:
        requests.post(recall_url, headers=headers).raise_for_status()
        logger.info(f"👋 Бот {leave_req.bot_id} покинул встречу!")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"🚨 Ошибка при попытке выгнать бота: {e}")
        return {"status": "error"}


# --- ЭНДПОИНТ 3: ПРИЕМ ВЕБХУКОВ ---
@app.post("/webhook/recall")
async def recall_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    event_type = payload.get("event")

    # Скрываем спам промежуточных вебхуков, оставляем только важное
    if event_type != "transcript.data":
        logger.info(f"\n🔔 Получен вебхук: {event_type}")

    if event_type == "bot.status_change":
        status = payload.get("data", {}).get("status")
        logger.info(f"🔄 Статус бота изменился на: {status}")

    elif event_type == "transcript.data":
        transcript_data = payload.get("data", {})
        speaker = transcript_data.get("speaker", "Спикер")
        words = transcript_data.get("words", [])
        is_final = transcript_data.get("is_final", False)  # Флаг завершенной фразы

        full_text = " ".join([word_info.get("text", "") for word_info in words]).strip()

        # Выводим в терминал ТОЛЬКО когда человек договорил предложение
        if full_text and is_final:
            background_tasks.add_task(log_transcript, speaker, full_text)

    elif event_type == "participant_events.join":
        name = payload.get("data", {}).get("name")
        logger.info(f"👤 К встрече подключился: {name}")

    return {"status": "ok"}