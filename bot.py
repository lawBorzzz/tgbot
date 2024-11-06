import os
import re
import json
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import openai

# Используй API-ключ ProxyAPI
PROXY_API_KEY = "sk-QxMDyszP1bCKSij5i9mx6pBVfG0xes5i"  # Ваш ключ
openai.api_key = PROXY_API_KEY
openai.api_base = "https://api.proxyapi.ru/openai/v1"

# ID администратора
ADMIN_ID = {1980610942}  # Замените на ваш Telegram ID для администратора

# Хранение истории сообщений для каждого пользователя
user_histories = {}

# Доступные модели и их цены
models = {
    "o1-preview": "3,00 ₽ за 1K токенов",
    "o1-mini": "0,864 ₽ за 1K токенов",
    "gpt-4o": "0,72 ₽ за 1K токенов",
    "gpt-4o-2024-05-13": "1,44 ₽ за 1K токенов",
    "gpt-4o-mini": "0,0432 ₽ за 1K токенов",
    "gpt-4-turbo": "2,88 ₽ за 1K токенов",
    "gpt-4": "8,64 ₽ за 1K токенов",
    "gpt-3.5-turbo-0125": "0,144 ₽ за 1K токенов",
    "gpt-3.5-turbo-1106": "0,30 ₽ за 1K токенов"
}

# Переменная для хранения текущей модели
current_model = "gpt-4o-mini"

# Имя файла JSON для хранения данных пользователей в той же папке, где скрипт
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(CURRENT_DIR, 'users.json')


# Инициализация JSON файла, если его нет
def init_json_file():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'w') as file:
            json.dump({}, file)

# Функция для чтения данных из JSON файла
def load_users_from_json():
    with open(USER_DATA_FILE, 'r') as file:
        return json.load(file)

# Функция для записи данных в JSON файл
def save_users_to_json(users):
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(users, file, indent=4)

# Функция для добавления пользователя в JSON файл
def add_user_to_json(user_id, username, access=False):
    users = load_users_from_json()
    users[user_id] = {"username": username, "access": access}
    save_users_to_json(users)

# Функция для обновления доступа
def update_user_access(user_id, access):
    users = load_users_from_json()
    if str(user_id) in users:
        users[str(user_id)]["access"] = access
        save_users_to_json(users)

# Функция для получения всех пользователей
def get_all_users():
    return load_users_from_json()

# Функция для получения пользователя по ID
def get_user_by_id(user_id):
    users = load_users_from_json()
    return users.get(str(user_id))

# Функция для проверки, является ли пользователь администратором
def is_admin(user_id):
    return user_id in ADMIN_ID

# Функция для проверки, есть ли пользователь в списке разрешенных
def is_allowed(user_id):
    user = get_user_by_id(user_id)
    return user and user["access"] or is_admin(user_id)

# Команда /start
async def start(update: Update, context):
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    user = get_user_by_id(user_id)
    if not user:
        add_user_to_json(user_id, username)  # Добавляем пользователя в JSON файл

    if is_allowed(user_id):
        await update.message.reply_text('Привет! Я бот от Borzzz. Задай мне вопрос.')
        if user_id not in user_histories:
            user_histories[user_id] = [{"role": "system", "content": "Ты помощник."}]
    else:
        await update.message.reply_text('Извините, у вас нет доступа к этому боту.')

# Команда /menu для отображения информации о текущей модели и количестве активных пользователей
async def menu(update: Update, context):
    # Определяем, откуда пришел запрос - из команды или из callback_query
    if update.message:  # Если вызов через команду /menu
        user_id = update.message.from_user.id
    elif update.callback_query:  # Если вызов через нажатие на кнопку "Назад"
        user_id = update.callback_query.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для просмотра меню.")
        return

    # Получаем текущую модель
    global current_model

    # Подсчитываем количество активных пользователей (с доступом)
    users = get_all_users()
    active_users_count = sum(1 for user in users.values() if user['access'])

    # Создаем кнопки меню
    buttons = [
        [InlineKeyboardButton("Пользователи", callback_data="menu:users")],
        [InlineKeyboardButton("Выбор модели", callback_data="menu:models")]
    ]

    # Формируем сообщение с текущей информацией
    menu_text = (
        f"Активная модель: {current_model}\n"
        f"Активных пользователей: {active_users_count}"
    )

    reply_markup = InlineKeyboardMarkup(buttons)

    # Отправляем сообщение в зависимости от того, откуда вызвана функция
    if update.message:  # Если вызов через команду
        await update.message.reply_text(menu_text, reply_markup=reply_markup)
    elif update.callback_query:  # Если вызов через callback (например, кнопка "Назад")
        # Проверяем, изменилось ли сообщение или кнопки
        if update.callback_query.message.text != menu_text:
            await update.callback_query.message.edit_text(menu_text, reply_markup=reply_markup)
        else:
            # Если содержимое не изменилось, отправляем новое сообщение
            await update.callback_query.message.edit_reply_markup(reply_markup=reply_markup)

# Обработка нажатий на кнопки в меню
async def menu_button_handler(update: Update, context):
    query = update.callback_query
    data = query.data

    if data == "menu:users":
        await show_users_menu(query, context)
    elif data == "menu:models":
        await show_models_menu(query)
    elif data == "menu:back":
        # Возвращаемся в главное меню
        await menu(update, context)

# Показ меню пользователей
async def show_users_menu(query, context):
    users = get_all_users()
    buttons = []
    for user_id, user_info in users.items():
        username = user_info['username']
        access = user_info['access']
        access_text = "да" if access else "нет"
        buttons.append([InlineKeyboardButton(f"{username} | Доступ: {access_text}", callback_data=f"user:{user_id}")])
        # buttons.append([InlineKeyboardButton(f"{username} (ID: {user_id}) | Доступ: {access_text}", callback_data=f"user:{user_id}")])

    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton("Назад", callback_data="menu:back")])

    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text("Список пользователей:", reply_markup=reply_markup)

# Показ меню моделей
async def show_models_menu(query):
    buttons = []
    for model, price in models.items():
        buttons.append([InlineKeyboardButton(f"{model} ({price})", callback_data=f"model:{model}")])

    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton("Назад", callback_data="menu:back")])

    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text("Выберите модель:", reply_markup=reply_markup)

# Обработка нажатий на кнопки пользователей и моделей
async def button_handler(update: Update, context):
    query = update.callback_query
    data = query.data

    if data.startswith("user:"):
        user_id = data.split(":")[1]
        await toggle_user_access(query, user_id)
    elif data.startswith("model:"):
        await choose_model(query, data.split(":")[1])

# Функция для изменения доступа пользователя
async def toggle_user_access(query, user_id):
    user = get_user_by_id(user_id)
    if user:
        username = user['username']
        access = user['access']
        new_access = not access  # Меняем доступ
        update_user_access(user_id, new_access)  # Обновляем доступ в JSON файле

        access_text = "Да" if new_access else "Нет"
        await query.edit_message_text(f"Доступ для {username} (ID: {user_id}) изменен на: {access_text}")

# Обработка выбора модели
async def choose_model(query, model):
    global current_model
    current_model = model  # Изменяем текущую модель
    await query.edit_message_text(f"Вы выбрали модель: {current_model}")

# Обработка сообщений
async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    if is_allowed(user_id):
        user_message = update.message.text

        if user_id not in user_histories:
            user_histories[user_id] = [{"role": "system", "content": "Ты помощник."}]

        user_histories[user_id].append({"role": "user", "content": user_message})

        try:
            # Отправляем запрос с выбранной моделью
            response = openai.ChatCompletion.create(
                model=current_model,
                messages=user_histories[user_id],
                max_tokens=1024
            )
            bot_reply = response['choices'][0]['message']['content']
            filtered_reply = latex_to_plain_text(bot_reply)
            user_histories[user_id].append({"role": "assistant", "content": filtered_reply})
            await update.message.reply_text(filtered_reply)
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {str(e)}")
    else:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")

# Обработка голосовых сообщений
async def handle_voice_message(update: Update, context):
    user_id = update.message.from_user.id
    if is_allowed(user_id):
        file_info = await context.bot.get_file(update.message.voice.file_id)  # Получаем информацию о голосовом сообщении
        voice_file = await file_info.download_as_bytearray()  # Загружаем файл как байтовый массив

        try:
            # Создаем временный файл для передачи в Whisper
            audio_file = io.BytesIO(voice_file)
            audio_file.name = "voice.ogg"  # Указываем имя файла с правильным расширением

            # Распознавание речи через Whisper
            transcription = openai.Audio.transcribe(
                file=audio_file,  # Передаем временный файл в OpenAI Whisper
                model="whisper-1"
            )

            user_message = transcription['text']
            
            # Обрабатываем расшифрованное сообщение как текстовое
            if user_id not in user_histories:
                user_histories[user_id] = [{"role": "system", "content": "Ты помощник."}]

            user_histories[user_id].append({"role": "user", "content": user_message})

            # Отправляем запрос с выбранной моделью
            response = openai.ChatCompletion.create(
                model=current_model,
                messages=user_histories[user_id],
                max_tokens=1024
            )

            bot_reply = response['choices'][0]['message']['content']
            filtered_reply = latex_to_plain_text(bot_reply)
            user_histories[user_id].append({"role": "assistant", "content": filtered_reply})
            await update.message.reply_text(filtered_reply)

        except Exception as e:
            await update.message.reply_text(f"Произошла ошибка: {e}")
    else:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")

# Преобразование LaTeX в обычный текст
def latex_to_plain_text(latex_str):
    # Обработка нижних индексов
    latex_str = re.sub(r'_\{([^\}]+)\}', lambda m: ''.join(['₀₁₂₃₄₅₆₇₈₉'[int(digit)] if digit.isdigit() else digit for digit in m.group(1)]), latex_str)
    latex_str = re.sub(r'_(\d)', lambda m: '₀₁₂₃₄₅₆₇₈₉'[int(m.group(1))], latex_str)

    # Обработка верхних индексов
    latex_str = re.sub(r'\^\{([^\}]+)\}', lambda m: ''.join(['⁰¹²³⁴⁵⁶⁷⁸⁹'[int(digit)] if digit.isdigit() else digit for digit in m.group(1)]), latex_str)
    latex_str = re.sub(r'\^(\d)', lambda m: '⁰¹²³⁴⁵⁶⁷⁸⁹'[int(m.group(1))], latex_str)

    # Замена математических операторов и специальных символов
    latex_str = latex_str.replace(r'\cdot', '⋅').replace(r'\times', '×').replace(r'\div', '÷')
    latex_str = latex_str.replace(r'\approx', '≈').replace(r'\infty', '∞').replace(r'\propto', '∝')
    latex_str = latex_str.replace(r'\neq', '≠').replace(r'\leq', '≤').replace(r'\geq', '≥')
    latex_str = latex_str.replace(r'\sim', '∼').replace(r'\cong', '≅').replace(r'\subset', '⊂').replace(r'\supset', '⊃')
    latex_str = latex_str.replace(r'\subseteq', '⊆').replace(r'\supseteq', '⊇').replace(r'\cup', '∪').replace(r'\cap', '∩')
    latex_str = latex_str.replace('^+', '⁺').replace('^-', '⁻')
    latex_str = re.sub(r'\\xrightarrow\{[^}]+\}', '→', latex_str)
    latex_str = re.sub(r'\\rightarrow', '→', latex_str)

    # Замена тригонометрических функций и логарифмов
    latex_str = latex_str.replace(r'\sin', 'sin').replace(r'\cos', 'cos').replace(r'\tan', 'tan')
    latex_str = latex_str.replace(r'\cot', 'cot').replace(r'\sec', 'sec').replace(r'\csc', 'csc')
    latex_str = latex_str.replace(r'\arcsin', 'arcsin').replace(r'\arccos', 'arccos').replace(r'\arctan', 'arctan')
    latex_str = latex_str.replace(r'\log', 'log').replace(r'\ln', 'ln')

    # Замена констант и специальных символов
    latex_str = latex_str.replace(r'\pi', 'π').replace(r'\sigma', 'σ').replace(r'\alpha', 'α')
    latex_str = latex_str.replace(r'\beta', 'β').replace(r'\varepsilon', 'ε').replace(r'\hbar', 'ℏ')
    latex_str = latex_str.replace(r'\nabla', '∇').replace(r'\partial', '∂')

    # Обработка операторов и функций для интегралов, сумм, произведений и пределов
    latex_str = re.sub(r'\\int', '∫', latex_str)
    latex_str = re.sub(r'\\iint', '∬', latex_str)
    latex_str = re.sub(r'\\oint', '∮', latex_str)
    latex_str = re.sub(r'\\sum', '∑', latex_str)
    latex_str = re.sub(r'\\prod', '∏', latex_str)
    latex_str = re.sub(r'\\lim', 'lim', latex_str)

    # Обработка модулей |...| и норм \|...\|
    latex_str = re.sub(r'\|([^|]+)\|', r'|\1|', latex_str)
    latex_str = re.sub(r'\\\|([^|]+)\\\|', r'‖\1‖', latex_str)

    # Обработка дробей \frac{числитель}{знаменатель} и вложенных скобок
    latex_str = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1) / (\2)', latex_str)
    latex_str = re.sub(r'\\left\(', '(', latex_str).replace(r'\right)', ')')  # Удаление лишних \left и \right

    # Замена для корней и других специальных функций
    latex_str = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', latex_str)
    latex_str = re.sub(r'\\sqrt\[([^\]]+)\]\{([^}]+)\}', r'√[\1](\2)', latex_str)  # Корень n-й степени

    # Замена для векторов и жирных символов (\mathbf и \mathbb)
    latex_str = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', latex_str)  # убирает \mathbf, делает текст обычным
    latex_str = re.sub(r'\\mathbb\{([^}]+)\}', r'\1', latex_str)  # убирает \mathbb, делает текст обычным

    # Замена для среднего арифметического и других статистических символов
    latex_str = re.sub(r'\\bar\{([^}]+)\}', r'ȳ', latex_str)  # пример: среднее значение \bar{x} -> x̄
    
    # Удаление оставшихся команд LaTeX и символов
    latex_str = re.sub(r'\\text\{([^}]+)\}', r'\1', latex_str)
    latex_str = re.sub(r'\\\((.*?)\\\)', r'\1', latex_str)
    latex_str = latex_str.replace("\\[", "").replace("\\]", "")
    latex_str = latex_str.replace(r'\,', ' ')  # Убирает пробелы \,
    latex_str = latex_str.replace(r'\&', '&').replace(r'\%', '%').replace(r'\_', '_').replace(r'\{', '{').replace(r'\}', '}')
    
    return latex_str

# Основная функция
def main():
    application = Application.builder().token("8188109483:AAHVgZLJkVf5YlAK_CMC_Z_D1N9QQLtt0i4").build()  # Вставьте свой токен

    # Инициализация файла JSON
    init_json_file()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))

    # Обработка кнопок в меню
    application.add_handler(CallbackQueryHandler(menu_button_handler, pattern="^menu:"))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработка всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
