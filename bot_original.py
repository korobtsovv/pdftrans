import os
import subprocess
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ==============================
# ВСТАВЬ СЮДА СВОЙ ТОКЕН БОТА
# ==============================
BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"

# Путь к твоему скрипту перевода
SCRIPT_PATH = "gpttranslate.py"

# Папка для временного хранения файлов
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "📄 Загрузите PDF файл, который нужно перевести.\n"
        "Я передам его в скрипт и отправлю вам переведённый файл."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    # Проверяем что это PDF
    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("⚠️ Пожалуйста, загрузите файл в формате PDF.")
        return

    await update.message.reply_text("⏳ Файл получен, начинаю перевод...")

    # Скачиваем файл
    original_name = document.file_name  # например: report.pdf
    input_path = os.path.join(DOWNLOAD_DIR, original_name)

    tg_file = await context.bot.get_file(document.file_id)
    await tg_file.download_to_drive(input_path)
    logger.info(f"Файл скачан: {input_path}")

    # Формируем имя выходного файла: report.pdf → report_en.pdf
    base_name = original_name[:-4]  # убираем .pdf
    output_name = f"{base_name}_en.pdf"
    output_path = os.path.join(DOWNLOAD_DIR, output_name)

    # Запускаем скрипт перевода
    try:
        result = subprocess.run(
            ["python", SCRIPT_PATH, input_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )

        if result.returncode != 0:
            logger.error(f"Ошибка скрипта: {result.stderr}")
            await update.message.reply_text(
                f"❌ Скрипт завершился с ошибкой:\n```\n{result.stderr[:1000]}\n```",
                parse_mode="Markdown"
            )
            return

    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Превышено время ожидания (5 минут). Попробуйте файл меньшего размера.")
        return
    except Exception as e:
        await update.message.reply_text(f"❌ Неожиданная ошибка: {e}")
        return

    # Проверяем что выходной файл создан
    if not os.path.exists(output_path):
        await update.message.reply_text(
            f"❌ Скрипт не создал файл `{output_name}`. "
            f"Убедитесь, что скрипт сохраняет результат в ту же папку с суффиксом `_en`.",
            parse_mode="Markdown"
        )
        return

    # Отправляем переведённый файл пользователю
    await update.message.reply_document(
        document=open(output_path, "rb"),
        filename=output_name,
        caption="✅ Перевод готов!"
    )
    logger.info(f"Файл отправлен: {output_name}")

    # Удаляем временные файлы
    os.remove(input_path)
    os.remove(output_path)


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Пожалуйста, загрузите PDF файл для перевода.")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other))

    logger.info("Бот запущен...")
    app.run_polling()
