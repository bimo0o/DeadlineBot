import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from datetime import datetime
import asyncio

TOKEN = '8199760860:AAGGUDgYGANFPNuX2fRHA1YWwgpOfbXpg0c'  # Замените на ваш токен
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ID главного модератора (ваш ID в Telegram)
MAIN_MODERATOR_ID = 712016596  # Замените на ваш Telegram ID

# Подключение к базе данных
conn = sqlite3.connect('deadlines.db')
cursor = conn.cursor()

# Создание таблиц для дедлайнов и модераторов
cursor.execute('''
    CREATE TABLE IF NOT EXISTS deadlines (
        id INTEGER PRIMARY KEY,
        description TEXT,
        deadline_date TEXT,
        notification_options TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS moderators (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE
    )
''')

conn.commit()

# Определение состояний для FSM
class AddDeadline(StatesGroup):
    waiting_for_date = State()
    waiting_for_description = State()
    waiting_for_notifications = State()
    waiting_for_delete = State()

# Создание роутера
router = Router()

# Функция для приветственного сообщения
@router.message(Command(commands=["start", "help"]))
async def send_welcome(message: types.Message):
    # Клавиатура для всех пользователей
    user_keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Показать дедлайны")],
        [KeyboardButton(text="Добавить дедлайн")],
        [KeyboardButton(text="Настройки уведомлений")]
    ], resize_keyboard=True)

    if message.from_user.id == MAIN_MODERATOR_ID:
        # Главное меню для главного модератора
        moderator_keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Добавить модератора")],
            [KeyboardButton(text="Показать дедлайны")],
            [KeyboardButton(text="Добавить дедлайн")],
            [KeyboardButton(text="Удалить дедлайн")],
            [KeyboardButton(text="Настройки уведомлений")]
        ], resize_keyboard=True)
        await message.answer("Привет, главный модератор! Выберите действие:", reply_markup=moderator_keyboard)
    else:
        cursor.execute("SELECT username FROM moderators WHERE username = ?", (message.from_user.username,))
        is_moderator = cursor.fetchone()
        if is_moderator:
            # Меню для модераторов
            moderator_keyboard = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="Показать дедлайны")],
                [KeyboardButton(text="Добавить дедлайн")],
                [KeyboardButton(text="Удалить дедлайн")],
                [KeyboardButton(text="Настройки уведомлений")]
            ], resize_keyboard=True)
            await message.answer("Привет, модератор! Выберите действие:", reply_markup=moderator_keyboard)
        else:
            await message.answer("Привет! Выберите действие:", reply_markup=user_keyboard)

# Начало добавления дедлайна: запрос даты и времени
@router.message(lambda message: message.text == "Добавить дедлайн")
async def start_adding_deadline(message: types.Message, state: FSMContext):
    await message.answer("Введите дату и время дедлайна в формате DD.MM.YYYY HH:MM:")
    await state.set_state(AddDeadline.waiting_for_date)

# Обработка введенной даты и времени
@router.message(AddDeadline.waiting_for_date)
async def process_deadline_date(message: types.Message, state: FSMContext):
    try:
        deadline_datetime = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(deadline_date=deadline_datetime)
        await message.answer("Теперь введите описание дедлайна:")
        await state.set_state(AddDeadline.waiting_for_description)
    except ValueError:
        await message.answer("Неправильный формат даты и времени. Пожалуйста, введите дату и время в формате DD.MM.YYYY HH:MM.")

# Обработка введенного описания дедлайна
@router.message(AddDeadline.waiting_for_description)
async def process_deadline_description(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    deadline_date = user_data['deadline_date']
    description = message.text
    # Сохранение дедлайна в базу данных без настроек уведомлений
    cursor.execute("INSERT INTO deadlines (description, deadline_date, notification_options) VALUES (?, ?, ?)",
                   (description, deadline_date.strftime("%Y-%m-%d %H:%M:%S"), ''))
    conn.commit()
    await message.answer(f"Дедлайн '{description}' успешно добавлен на {deadline_date.strftime('%d.%m.%Y %H:%M')}.")
    await send_welcome(message)  # Возврат в главное меню после добавления
    await state.clear()

# Обработчик кнопки "Показать дедлайны"
@router.message(lambda message: message.text == "Показать дедлайны")
async def show_deadlines(message: types.Message):
    cursor.execute("SELECT id, description, deadline_date FROM deadlines ORDER BY deadline_date")
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Список дедлайнов:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                if len(date) == 10:
                    date += ' 00:00:00'
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                response += (f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата и время: {deadline_date}\n\n")
            except ValueError:
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата: {date} (Неправильный формат)\n\n"
        await message.answer(response)
    else:
        await message.answer("Нет активных дедлайнов.")

# Удаление дедлайна
@router.message(lambda message: message.text == "Удалить дедлайн")
async def delete_deadline(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, description, deadline_date FROM deadlines ORDER BY deadline_date")
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Выберите номер дедлайна, который хотите удалить:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                response += (f"#{idx} - Описание: {desc}, Дата и время: {deadline_date}\n")
            except ValueError:
                response += f"#{idx} - Описание: {desc}, Дата: {date} (Неправильный формат)\n"
        await message.answer(response)
        await state.set_state(AddDeadline.waiting_for_delete)
    else:
        await message.answer("Нет дедлайнов для удаления.")

# Обработка выбора номера дедлайна для удаления
@router.message(AddDeadline.waiting_for_delete)
async def process_delete_deadline(message: types.Message, state: FSMContext):
    try:
        selected_deadline_idx = int(message.text.strip()) - 1
        cursor.execute("SELECT id FROM deadlines ORDER BY deadline_date")
        deadlines = cursor.fetchall()
        if 0 <= selected_deadline_idx < len(deadlines):
            deadline_id = deadlines[selected_deadline_idx][0]
            cursor.execute("DELETE FROM deadlines WHERE id = ?", (deadline_id,))
            conn.commit()
            await message.answer("Дедлайн успешно удален.")
            await send_welcome(message)  # Возврат в главное меню после удаления
        else:
            await message.answer("Неверный номер дедлайна. Пожалуйста, попробуйте еще раз.")
    except ValueError:
        await message.answer("Неверный ввод. Пожалуйста, введите номер дедлайна.")
    await state.clear()

# Обработчик кнопки "Настройки уведомлений"
@router.message(lambda message: message.text == "Настройки уведомлений")
async def notification_settings(message: types.Message, state: FSMContext):
    # Получаем выбранные уведомления из состояния (если ранее уже выбраны)
    user_data = await state.get_data()
    selected_notifications = user_data.get("selected_notifications", [])

    # Определяем статус уведомлений
    def get_status(option):
        return "[Активно]" if option in selected_notifications else "[Неактивно]"

    await message.answer(
        "Выберите, за сколько времени вы хотите получать уведомления:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"Уведомить за 1 час до конца {get_status('1 час')}")],
                [KeyboardButton(text=f"Уведомить за 1 день до конца {get_status('1 день')}")],
                [KeyboardButton(text=f"Уведомить за 2 дня до конца {get_status('2 дня')}")],
                [KeyboardButton(text=f"Уведомить за 3 дня до конца {get_status('3 дня')}")],
                [KeyboardButton(text=f"Уведомить за 1 неделю до конца {get_status('1 неделя')}")],
                [KeyboardButton(text="Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    )

# Обработка кнопки "Назад" для возврата в главное меню
@router.message(lambda message: message.text == "Назад")
async def go_back_to_main_menu(message: types.Message):
    await send_welcome(message)

# Функция для добавления модераторов (доступна только главному модератору)
@router.message(lambda message: message.text == "Добавить модератора" and message.from_user.id == MAIN_MODERATOR_ID)
async def request_moderator_username(message: types.Message):
    await message.answer("Введите никнейм пользователя, которого хотите добавить модератором, в формате @nickname:")

# Функция для сохранения модератора
@router.message(lambda message: message.text.startswith('@') and message.from_user.id == MAIN_MODERATOR_ID)
async def add_moderator(message: types.Message):
    username = message.text.strip()
    cursor.execute("SELECT username FROM moderators WHERE username = ?", (username,))
    moderator_exists = cursor.fetchone()
    if moderator_exists:
        await message.answer(f"Пользователь {username} уже является модератором.")
    else:
        cursor.execute("INSERT INTO moderators (username) VALUES (?)", (username,))
        conn.commit()
        await message.answer(f"Пользователь {username} успешно добавлен в модераторы.")

# Регистрация роутера
dp.include_router(router)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    dp.run_polling(bot)
