import os
import subprocess
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ==============================
# ВСТАВЬ СЮДА СВОЙ ТОКЕН БОТА
# ==============================
BOT_TOKEN = "blablabla"

# Путь к твоему скрипту перевода
SCRIPT_PATH = "translate.py"

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
        "👋 Привіт кохана!❤️❤️❤️\n\n"
        "📄 Завантаж PDF файл, котрий треба перекласти."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    # Проверяем что это PDF
    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("⚠️ Будь ласка, завантажте файл у форматі PDF.")
        return

    await update.message.reply_text("⏳ Файл отримано, починаю переклад...❤️")

    # Скачиваем файл
    original_name = document.file_name  # например: report.pdf
    input_path = os.path.join(DOWNLOAD_DIR, original_name)

    tg_file = await context.bot.get_file(document.file_id)
    await tg_file.download_to_drive(input_path)
    logger.info(f"Файл завантажено: {input_path}")

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
            logger.error(f"Помилка скрипта: {result.stderr}")
            await update.message.reply_text(
                f"❌ Скрипт завершився з помилкою:\n```\n{result.stderr[:1000]}\n```",
                parse_mode="Markdown"
            )
            return

    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Перевищено час очікування (5 хвилин). Спробуйте файл меншого розміру.")
        return
    except Exception as e:
        await update.message.reply_text(f"❌ Несподівана помилка: {e}")
        return

    # Проверяем что выходной файл создан
    if not os.path.exists(output_path):
        await update.message.reply_text(
            f"❌ Скрипт не створив файл `{output_name}`. "
            f"Переконайтеся, що скрипт зберігає результат у ту саму папку із суфіксом `_en`.",
            parse_mode="Markdown"
        )
        return

    # Отправляем переведённый файл пользователю
    await update.message.reply_document(
        document=open(output_path, "rb"),
        filename=output_name,
        caption="✅ Переклад завершено! Кохаю 😘"
    )
    logger.info(f"Файл отправлен: {output_name}")

    # Удаляем временные файлы
    os.remove(input_path)
    os.remove(output_path)


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Будь ласка, завантажте PDF-файл для перекладу.")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other))

    logger.info("Бот запущен...")
    app.run_polling()