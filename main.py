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

TOKEN = '8199760860:AAGGUDgYGANFPNuX2fRHA1YWwgpOfbXpg0c'
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ID главного модератора (ваш ID в Telegram)
MAIN_MODERATOR_ID = 712016596  # Замените на ваш Telegram ID

# Подключение к базе данных
conn = sqlite3.connect('deadlines.db')
cursor = conn.cursor()

# Создание таблиц для дедлайнов и модераторов
cursor.execute('''CREATE TABLE IF NOT EXISTS deadlines
                  (id INTEGER PRIMARY KEY, description TEXT, deadline_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS moderators
                  (id INTEGER PRIMARY KEY, username TEXT UNIQUE)''')
conn.commit()


# Определение состояний для FSM
class AddDeadline(StatesGroup):
    waiting_for_date = State()
    waiting_for_description = State()
    waiting_for_delete = State()


# Создание роутера
router = Router()


# Функция для приветственного сообщения
@router.message(Command(commands=["start", "help"]))
async def send_welcome(message: types.Message):
    user_keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Показать дедлайны")],
        [KeyboardButton(text="Добавить дедлайн")],
        [KeyboardButton(text="Удалить дедлайн")]
    ], resize_keyboard=True)

    if message.from_user.id == MAIN_MODERATOR_ID:
        moderator_keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Добавить модератора")],
            [KeyboardButton(text="Показать дедлайны")],
            [KeyboardButton(text="Добавить дедлайн")],
            [KeyboardButton(text="Удалить дедлайн")]
        ], resize_keyboard=True)
        await message.answer("Привет, главный модератор! Выберите действие:", reply_markup=moderator_keyboard)
    else:
        await message.answer("Привет! Выберите действие:", reply_markup=user_keyboard)


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

                response += (
                    f"Дедлайн #{idx}:\n"
                    f"- Описание: {desc}\n"
                    f"- Дата и время: {deadline_date}\n\n"
                )
            except ValueError as e:
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата: {date} (Неправильный формат)\n\n"

        await message.answer(response)
    else:
        await message.answer("Нет активных дедлайнов.")


@router.message(lambda message: message.text == "Удалить дедлайн")
async def start_delete_deadline(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, description FROM deadlines ORDER BY deadline_date")
    deadlines = cursor.fetchall()

    if deadlines:
        response = "Выберите дедлайн для удаления:\n"
        for idx, (deadline_id, desc) in enumerate(deadlines, 1):
            response += f"{idx}. {desc}\n"  # Убираем "Дедлайн #" из вывода

        response += "\nВведите номер дедлайна для удаления:"
        await message.answer(response)

        # Устанавливаем состояние для ожидания номера дедлайна
        await state.set_state(AddDeadline.waiting_for_delete)
    else:
        await message.answer("Нет активных дедлайнов для удаления.")


# Обработка выбора дедлайна для удаления
@router.message(AddDeadline.waiting_for_delete)
async def process_deadline_deletion(message: types.Message):
    try:
        deadline_index = int(message.text) - 1  # Преобразуем номер в индекс
        cursor.execute("SELECT id FROM deadlines ORDER BY deadline_date")
        deadlines = cursor.fetchall()

        if 0 <= deadline_index < len(deadlines):
            deadline_id = deadlines[deadline_index][0]
            cursor.execute("DELETE FROM deadlines WHERE id = ?", (deadline_id,))
            conn.commit()
            await message.answer("Дедлайн успешно удален.")
        else:
            await message.answer("Неверный номер дедлайна. Пожалуйста, попробуйте еще раз.")
    except ValueError:
        await message.answer("Пожалуйста, введите номер дедлайна для удаления.")


# Начало добавления дедлайна: запрос даты и времени
@router.message(lambda message: message.text == "Добавить дедлайн")
async def start_adding_deadline(message: types.Message, state: FSMContext):
    await message.answer("Введите дату и время дедлайна в формате DD.MM.YYYY HH:MM:")
    await state.set_state(AddDeadline.waiting_for_date)


# Обработка введенной даты и времени
@router.message(AddDeadline.waiting_for_date)
async def process_deadline_date(message: types.Message, state: FSMContext):
    await message.answer(f"Получены дата и время: {message.text}")
    try:
        deadline_datetime = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(deadline_date=deadline_datetime)
        await message.answer("Теперь введите описание дедлайна:")
        await state.set_state(AddDeadline.waiting_for_description)
    except ValueError:
        await message.answer(
            "Неправильный формат даты и времени. Пожалуйста, введите дату и время в формате DD.MM.YYYY HH:MM.")


# Обработка введенного описания дедлайна
@router.message(AddDeadline.waiting_for_description)
async def process_deadline_description(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    deadline_date = user_data['deadline_date']
    description = message.text
    cursor.execute("INSERT INTO deadlines (description, deadline_date) VALUES (?, ?)", (description, deadline_date))
    conn.commit()
    await message.answer(f"Дедлайн '{description}' успешно добавлен на {deadline_date}.")
    await state.clear()


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


# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
