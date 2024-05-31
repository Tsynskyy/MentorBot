from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from pymongo import MongoClient
from datetime import datetime
import pytz
import os

from check_list import today_main_tasks, skip_adaptation_day, return_skipped_day, view_planner, complete_task, postpone_task, send_progress_chart

MONGO_URI = os.getenv('MONGO_URI')

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.HSE_BOT
users = db.Users


def get_name(update, users):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.message.from_user.id

    user_data = users.find_one({"_id": user_id})

    if user_data:
        name = user_data.get("name")
        return name
    return None


def get_main_menu_keyboard():
    return [
        [InlineKeyboardButton("FAQ и Информация", callback_data='FAQ'),
         InlineKeyboardButton("Чек-лист Адаптации", callback_data='check_list')],
        [InlineKeyboardButton("Прогресс адаптации", callback_data='send_progress_chart'),
         InlineKeyboardButton("Ещё Опции", callback_data='Options')]
    ]


def get_check_list_menu_keyboard():
    return [
        [InlineKeyboardButton("Сегодня", callback_data='today_main_tasks'),
         InlineKeyboardButton("Ежедневник", callback_data='view_planner')],
        [InlineKeyboardButton("Отложить на один день", callback_data='skip_adaptation_day'),
         InlineKeyboardButton("Вернуть отложенный день", callback_data='return_skipped_day')],
        [InlineKeyboardButton("Назад", callback_data='back')]
    ]


async def show_menu(update: Update, context: CallbackContext):
    moscow_tz = pytz.timezone('Europe/Moscow')

    moscow_time = datetime.now(moscow_tz)

    hour = moscow_time.hour
    if 5 <= hour < 12:
        greeting = "Доброе утро"
    elif 12 <= hour < 17:
        greeting = "Добрый день"
    else:
        greeting = "Добрый вечер"

    name = get_name(update, users)

    text = f'{greeting}, {name}!'

    reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)


async def handle_callback(update: Update, context: CallbackContext, callback_data: str):
    if callback_data == 'back':
        await show_menu(update, context)
    elif callback_data == 'today_main_tasks':
        await today_main_tasks(update, context)
    elif callback_data == 'skip_adaptation_day':
        await skip_adaptation_day(update, context)
    elif callback_data == 'return_skipped_day':
        await return_skipped_day(update, context)
    elif callback_data == 'view_planner':
        await view_planner(update, context)
    elif callback_data.startswith('complete_task_'):
        await complete_task(update, context)
    elif callback_data.startswith('postpone_task_'):
        await postpone_task(update, context)
    elif callback_data == 'send_progress_chart':
        await send_progress_chart(update, context)
    else:
        await handle_additional_options(update, context, callback_data)


async def handle_additional_options(update: Update, context: CallbackContext, callback_data: str):
    if callback_data == 'FAQ':
        await send_faq_document(update, context)
    elif callback_data == 'check_list':
        await show_adaptation_checklist(update, context)
    elif callback_data == 'Options':
        await show_options(update, context)
    else:
        await update.callback_query.edit_message_text(text="Unknown option.")


async def send_faq_document(update: Update, context: CallbackContext):
    with open("Files\\file1.pdf", 'rb') as file:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=file)
    back_button = InlineKeyboardButton("Назад", callback_data='back')
    reply_markup = InlineKeyboardMarkup([[back_button]])
    await update.callback_query.edit_message_text(text="FAQ и Информация", reply_markup=reply_markup)


async def show_adaptation_checklist(update: Update, context: CallbackContext):
    reply_markup = InlineKeyboardMarkup(get_check_list_menu_keyboard())
    await update.callback_query.edit_message_text(text="Чек-лист Адаптации", reply_markup=reply_markup)


async def show_options(update: Update, context: CallbackContext):
    back_button = InlineKeyboardButton("Назад", callback_data='back')
    reply_markup = InlineKeyboardMarkup([[back_button]])
    await update.callback_query.edit_message_text(text="Ещё Опции", reply_markup=reply_markup)


async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    await handle_callback(update, context, callback_data)
