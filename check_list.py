from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from pymongo import MongoClient
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from telegram import InputFile
import tempfile
from matplotlib.ticker import MaxNLocator
import os

MONGO_URI = os.getenv('MONGO_URI')

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.HSE_BOT
users = db.Users
adaptation = db.Adaptation
daily_tasks = db.DailyTasks  # коллекция для ежедневных задач
planner = db.Planner  # коллекция для задач ежедневника
user_planner = db.User_Planner  # коллекция для отслеживания выполнения задач


def count_weekends(start_date, end_date):
    weekends = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() >= 5:  # Суббота или воскресенье
            weekends += 1
        current_date += timedelta(days=1)
    return weekends


async def get_adaptation_day(user_data):
    start_date = user_data.get("start_date")
    skipped_days = user_data.get("skipped_days", 0)

    if not start_date:
        return None, "Не удалось найти дату начала работы."

    start_date = datetime.strptime(start_date, "%d.%m.%Y")
    current_date = datetime.now()

    # Подсчет выходных с начала работы до текущей даты
    weekends = count_weekends(start_date, current_date)

    # Порядковый день адаптации с учетом пропущенных дней и выходных
    total_days_since_start = (current_date - start_date).days + 1
    adaptation_day = total_days_since_start - skipped_days - weekends

    # Проверка на выходной день
    if current_date.weekday() >= 5:  # Суббота или воскресенье
        return None, "Сегодня выходной."

    return adaptation_day, None


async def today_main_tasks(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    await update.callback_query.answer()

    user_data = users.find_one({"_id": user_id})
    adaptation_day, error_message = await get_adaptation_day(user_data)

    if error_message:
        keyboard = []
        back_button = InlineKeyboardButton("Назад", callback_data='check_list')
        keyboard.append([back_button])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(text=error_message, reply_markup=reply_markup)
        return

    tasks_data = daily_tasks.find_one({"day": adaptation_day})
    tasks = tasks_data.get("tasks", []) if tasks_data else []

    keyboard = []

    if not tasks:
        response_text = "Сегодня нет задач."
    else:
        response_text = "Твои главные задачи на сегодня:\n" + \
            "\n".join(f"{i+1}. {task}" for i, task in enumerate(tasks))

    back_button = InlineKeyboardButton("Назад", callback_data='check_list')
    keyboard.append([back_button])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)


async def skip_adaptation_day(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    await update.callback_query.answer()

    user_data = users.find_one({"_id": user_id})
    start_date = user_data.get("start_date")

    if not start_date:
        response_text = "Не удалось найти дату начала работы."
        back_button = InlineKeyboardButton("Назад", callback_data='check_list')
        keyboard = [[back_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)
        return

    start_date = datetime.strptime(start_date, "%d.%m.%Y")
    current_date = datetime.now()

    # Подсчет выходных с начала работы до текущей даты
    weekends = count_weekends(start_date, current_date)

    # Проверка на превышение количества пропущенных дней
    total_days_since_start = (current_date - start_date).days + 1
    skipped_days = user_data.get("skipped_days", 0)
    working_days_since_start = total_days_since_start - weekends

    if skipped_days >= working_days_since_start:
        response_text = "Количество пропущенных дней не может превышать количество рабочих дней с начала работы."
        back_button = InlineKeyboardButton("Назад", callback_data='check_list')
        keyboard = [[back_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)
        return

    users.update_one({"_id": user_id}, {
                     "$inc": {"skipped_days": 1}}, upsert=True)
    response_text = "Один день адаптации был пропущен."
    back_button = InlineKeyboardButton("Назад", callback_data='check_list')
    keyboard = [[back_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)


async def return_skipped_day(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    await update.callback_query.answer()

    user_data = users.find_one({"_id": user_id})
    skipped_days = user_data.get("skipped_days", 0)

    if skipped_days <= 0:
        response_text = "Нет пропущенных дней для возврата."
        back_button = InlineKeyboardButton("Назад", callback_data='check_list')
        keyboard = [[back_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)
        return

    users.update_one({"_id": user_id}, {
                     "$inc": {"skipped_days": -1}}, upsert=True)
    response_text = "Один пропущенный день был возвращен."
    back_button = InlineKeyboardButton("Назад", callback_data='check_list')
    keyboard = [[back_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)


async def view_planner(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    await update.callback_query.answer()

    user_data = users.find_one({"_id": user_id})
    adaptation_day, error_message = await get_adaptation_day(user_data)

    if error_message:
        response_text = error_message
        back_button = InlineKeyboardButton("Назад", callback_data='check_list')
        keyboard = [[back_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)
        return

    tasks_data = planner.find_one({"day": adaptation_day})
    tasks = tasks_data.get("tasks", []) if tasks_data else []

    user_tasks = user_planner.find_one({"user_id": user_id, "day": adaptation_day}) or {
        "completed_tasks": [], "postponed_tasks": []}

    keyboard = []
    response_text = "Твои задачи на сегодня:\n"
    task_index = 0

    # Отображение текущих задач
    for task in tasks:
        task_index += 1
        contact_info = f" (Контакт: {
            task['contact']})" if task['contact'] else ""
        if task_index in user_tasks.get("completed_tasks", []):
            response_text += f"\n\n🟢 {task_index}. {
                task['time']} - {task['task']}{contact_info}"
            keyboard.append([
                InlineKeyboardButton(f"Отметить как невыполненную #{
                                     task_index}", callback_data=f'complete_task_{adaptation_day}_{task_index}')
            ])
        elif task_index not in user_tasks.get("postponed_tasks", []):
            response_text += f"\n\n⚪️ {task_index}. {
                task['time']} - {task['task']}{contact_info}"
            keyboard.append([
                InlineKeyboardButton(f"Выполнить задачу #{
                                     task_index}", callback_data=f'complete_task_{adaptation_day}_{task_index}'),
                InlineKeyboardButton(f"Отложить задачу #{
                                     task_index}", callback_data=f'postpone_task_{adaptation_day}_{task_index}')
            ])

    # Отображение отложенных задач
    postponed_tasks = [tasks[i-1]
                       for i in user_tasks.get("postponed_tasks", [])]
    if postponed_tasks:
        response_text += "\n\nОтложенные задачи:\n"
        for task in postponed_tasks:
            task_index = tasks.index(task) + 1
            contact_info = f" (Контакт: {
                task['contact']})" if task['contact'] else ""
            response_text += f"\n\n⏳ {task_index}. {
                task['time']} - {task['task']}{contact_info}"
            keyboard.append([
                InlineKeyboardButton(f"Выполнить задачу #{
                                     task_index}", callback_data=f'complete_task_{adaptation_day}_{task_index}')
            ])

    if not tasks and not postponed_tasks:
        response_text += "\nСегодня нет задач."

    back_button = InlineKeyboardButton("Назад", callback_data='check_list')
    keyboard.append([back_button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=response_text, reply_markup=reply_markup)


async def complete_task(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_')
    adaptation_day = int(data[2])
    task_index = int(data[-1])

    user_tasks = user_planner.find_one({"user_id": user_id, "day": adaptation_day}) or {
        "completed_tasks": [], "postponed_tasks": []}

    if task_index in user_tasks.get("completed_tasks", []):
        user_tasks["completed_tasks"].remove(task_index)
    else:
        user_tasks["completed_tasks"].append(task_index)
        if task_index in user_tasks.get("postponed_tasks", []):
            user_tasks["postponed_tasks"].remove(task_index)

    user_planner.update_one({"user_id": user_id, "day": adaptation_day}, {
                            "$set": user_tasks}, upsert=True)
    await view_planner(update, context)


async def postpone_task(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split('_')
    adaptation_day = int(data[2])
    task_index = int(data[-1])

    user_tasks = user_planner.find_one({"user_id": user_id, "day": adaptation_day}) or {
        "completed_tasks": [], "postponed_tasks": []}

    if task_index not in user_tasks.get("postponed_tasks", []):
        user_tasks["postponed_tasks"].append(task_index)

    user_planner.update_one({"user_id": user_id, "day": adaptation_day}, {
                            "$set": user_tasks}, upsert=True)
    await view_planner(update, context)


def get_all_users_progress():
    all_users = users.find()
    all_progress = {}
    user_counter = 1  # нумерация сотрудников

    for user in all_users:
        user_id = user["_id"]
        name = f"Сотрудник{user_counter}"
        user_counter += 1
        start_date = datetime.strptime(user.get("start_date"), "%d.%m.%Y")
        current_date = datetime.now()
        total_days = (current_date - start_date).days + 1

        progress = []

        for day in range(1, total_days + 1):
            day_tasks = user_planner.find_one({"user_id": user_id, "day": day}) or {
                "completed_tasks": []}
            completed_tasks_count = len(day_tasks.get("completed_tasks", []))
            progress.append((day, completed_tasks_count))

        all_progress[name] = progress

    return all_progress


def create_all_users_progress_chart(all_progress):
    plt.figure(figsize=(14, 8))

    for name, progress in all_progress.items():
        days, completed_tasks = zip(*progress) if progress else ([], [])
        plt.plot(days, completed_tasks, marker='o',
                 linestyle='-', label=f'{name}')

    plt.xlabel('Дни адаптации')
    plt.ylabel('Количество выполненных задач')
    plt.title('Прогресс адаптации всех пользователей')
    plt.legend(title="Пользователи", loc='upper right')
    plt.grid(True)

    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(temp_file.name)
    plt.close()

    return temp_file.name


async def send_progress_chart(update: Update, context: CallbackContext):
    await update.callback_query.answer()

    all_progress = get_all_users_progress()
    chart_path = create_all_users_progress_chart(all_progress)

    with open(chart_path, 'rb') as chart:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(chart))

    import os
    os.remove(chart_path)
