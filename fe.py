import asyncio
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand
import logging
from config_reader import config
import queue  # Используем queue.Queue вместо multiprocessing.Queue

# Логирование
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.TG_token.get_secret_value())

# Глобальные переменные
myuser_id = 578651553
mygroup_id = 229734873
chatId = 210531192
last_message = None
subscribed_users = set()  # Список пользователей, подписанных на автоматические уведомления
message_queue = queue.Queue()  # Очередь для сообщений из VK

# Инициализация Telegram-бота
# bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# Установка команд бота
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Начать работу"),
        BotCommand(command="/rasp", description="Посмотреть расписание"),
        BotCommand(command="/subscribe", description="Подписаться на автоматические уведомления"),
        BotCommand(command="/unsubscribe", description="Отписаться от автоматических уведомлений"),
    ]
    await bot.set_my_commands(commands)

# Команда /start
@dp.message(Command("start"))
async def command_start_handler(message: types.Message):
    await message.answer("Привет! Используйте меню команд для взаимодействия.")

# Команда /rasp
def create_rasp_handler():
    async def command_rasp_handler(message: types.Message):
        global last_message
        logging.info("Обработка команды /rasp")
        if not message_queue.empty():
            msg = message_queue.get()
            last_message = msg
            await message.answer(f"Расписание:\n{msg}")
        elif last_message is not None:
            await message.answer(f"Расписание:\n{last_message}")
        else:
            await message.answer("Сообщение ещё не получено.")
    return command_rasp_handler

# Команда /subscribe
@dp.message(Command("subscribe"))
async def command_subscribe_handler(message: types.Message):
    user_id = message.from_user.id
    subscribed_users.add(user_id)
    await message.answer("Вы успешно подписались на автоматические уведомления о расписании.")

# Команда /unsubscribe
@dp.message(Command("unsubscribe"))
async def command_unsubscribe_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in subscribed_users:
        subscribed_users.remove(user_id)
        await message.answer("Вы успешно отписались от автоматических уведомлений.")
    else:
        await message.answer("Вы не подписаны на автоматические уведомления.")

# Фоновая задача для проверки очереди
async def background_task():
    while True:
        await asyncio.sleep(60)  # Проверка каждые 60 секунд
        if not message_queue.empty():
            new_message = message_queue.get()
            global last_message
            last_message = new_message
            for user_id in subscribed_users:
                try:
                    await bot.send_message(user_id, f"Автоматическое обновление расписания:\n{new_message}")
                except Exception as e:
                    logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

# Функция для прослушивания событий VK
def listen_vk_updates():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    vk_session = vk_api.VkApi(token=config.VK_token.get_secret_value())
    longpoll = VkLongPoll(vk_session, mode=64)
    logging.info("Начинаем прослушивание событий VK...")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.group_id
            if user_id == chatId:
                msg = event.text.strip()
                logging.info(f"Новое сообщение от пользователя {user_id}: {msg}")
                try:
                    message_queue.put(msg)  # Добавляем сообщение в очередь
                    logging.info(f"Сообщение добавлено в очередь: {msg}")
                except Exception as e:
                    logging.error(f"Ошибка при добавлении сообщения в очередь: {e}")

# Основная функция
async def main():
    # Запускаем процесс для прослушивания VK
    vk_thread = threading.Thread(target=listen_vk_updates)
    vk_thread.start()

    # Устанавливаем команды бота
    await set_commands(bot)

    # Регистрируем обработчик команды /rasp
    dp.message.register(create_rasp_handler(), Command("rasp"))

    # Запускаем фоновую задачу
    asyncio.create_task(background_task())

    # Запуск Telegram-бота
    await dp.start_polling(bot)

# Точка входа в программу
if __name__ == "__main__":
    import threading
    asyncio.run(main())