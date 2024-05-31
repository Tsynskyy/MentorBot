import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from pymongo import MongoClient
from dotenv import load_dotenv
from Menu.menu import show_menu, button_callback

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
BOT_TOKEN = os.getenv('BOT_TOKEN')

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.HSE_BOT
users = db.Users


def user_exists(user_id, users_collection):
    user_data = users_collection.find_one({"_id": user_id})
    return user_data is not None


async def handle_messages(update, context):
    user_id = update.message.from_user.id

    if not user_exists(user_id, users):
        await update.message.reply_text("Кажется, у меня нет твоих данных. Пожалуйста, обратись к администратору.")
    else:
        await show_menu(update, context)


def setup_handlers(application):
    menu_handler = CommandHandler('menu', show_menu)
    application.add_handler(menu_handler)

    button_handler = CallbackQueryHandler(button_callback)
    application.add_handler(button_handler)

    messages_handler = MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_messages)
    application.add_handler(messages_handler)


def run_bot():
    print("Бот запускается")

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    setup_handlers(application)

    print("Бот запущен")

    try:
        application.run_polling()
    except KeyboardInterrupt:
        print("Останавливаю бота, пожалуйста, подождите...")
        application.stop()
        print("Бот был остановлен вручную.")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
    finally:
        print("Завершение работы бота.")


if __name__ == '__main__':
    run_bot()
