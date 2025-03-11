import os
import asyncio
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types.message import ContentType
from aiogram.types import LabeledPrice

# Настройки бота (замените на свои значения)
TOKEN = "8016688198:AAGasnaGyL3R45JUoDraOwsmpO0vpg31NBs"  # Токен бота от @BotFather
PAYMENT_TOKEN = "1877036958:TEST:7614551863"  # Тестовый платежный токен (замените на свой)
OWNER_ID = 7614551863  # Ваш ID в Telegram (можно узнать через @userinfobot)

# Инициализация бота с поддержкой платежей
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Словари для хранения данных пользователей
user_orders = {}  # Заказы пользователей
active_orders = {}  # Активные заказы
pending_payments = {}  # Ожидающие оплаты заказы

# Словарь для хранения состояний пользователей (вместо FSMContext для других пользователей)
user_states_dict = {}

# Словарь для хранения времени последнего заказа пользователя
user_last_order_time = {}

# Состояния пользователя
class States(StatesGroup):
    IDLE = State()
    WAITING_FOR_ORDER_DESCRIPTION = State()
    WAITING_FOR_PRICE = State()
    WAITING_FOR_SUPPORT_MESSAGE = State()
    WAITING_FOR_OWNER_RESPONSE = State()
    WAITING_FOR_PHOTO = State()
    WAITING_FOR_PAYMENT = State()

# Функция для создания главного меню
def create_main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Сделать заказ")
    builder.button(text="Пригласить друга")
    builder.button(text="Тех. поддержка")
    
    # Добавляем кнопку "Заказы" только для владельца
    if user_id == OWNER_ID:
        builder.button(text="Заказы")
        builder.adjust(2, 2)
    else:
        builder.adjust(1, 2)
    
    return builder.as_markup(resize_keyboard=True)

# Функция для создания платежной клавиатуры
def payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить звездами", pay=True)
    return builder.as_markup()

# Обработчик команды /start
@dp.message(Command("start"))
async def start_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, есть ли параметры в команде start
    if len(message.text.split()) > 1:
        params = message.text.split()[1]
        
        # Проверяем, является ли это командой для отправки звезд
        if params.startswith("stars_"):
            try:
                # Извлекаем количество звезд
                stars_amount = int(params.split("_", 1)[1])
                
                # Отправляем инструкцию по отправке звезд
                stars_instructions = f"""
Для отправки {stars_amount} звезд:

1. Нажмите на иконку ⭐️ внизу экрана
2. Выберите количество: {stars_amount}
3. Отправьте звезды боту
4. Вернитесь в предыдущее сообщение и нажмите "Я уже отправил звезды"
"""
                
                await message.answer(stars_instructions)
                return
            except Exception as e:
                print(f"Ошибка при обработке команды отправки звезд: {e}")
        
        # Проверяем, является ли это командой оплаты
        elif params.startswith("pay_"):
            try:
                # Извлекаем ID заказа
                order_id = params.split("_", 1)[1]
                
                # Проверяем, существует ли заказ
                if order_id not in active_orders:
                    await message.answer("Заказ не найден или уже оплачен.")
                    return
                
                price = active_orders[order_id]['price']
                
                # Отправляем инструкцию по оплате
                payment_instructions = f"""
Для оплаты заказа #{order_id} отправьте {price} звезд этому боту.

После отправки звезд вернитесь в предыдущее сообщение и нажмите кнопку "Я уже отправил звезды".
"""
                
                await message.answer(payment_instructions)
                return
            except Exception as e:
                print(f"Ошибка при обработке команды оплаты: {e}")
    
    # Стандартная обработка команды /start
    await state.set_state(States.IDLE)
    
    # Отправляем приветственное сообщение с фото
    try:
        from aiogram.types import FSInputFile
        photo = FSInputFile('welcome.jpg')
        
        await message.answer_photo(
            photo=photo, 
            caption="Добро пожаловать в Chappos Design - Сделать Заказ!\n\nВыберите действие из меню ниже:",
            reply_markup=create_main_menu(user_id)
        )
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")
        await message.answer(
            "Добро пожаловать в Chappos Design - Сделать Заказ!\n\nВыберите действие из меню ниже:",
            reply_markup=create_main_menu(user_id)
        )

# Обработчик кнопки "Сделать заказ"
@dp.message(F.text == "Сделать заказ")
async def make_order(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_time = time.time()
    
    # Проверяем, не отправлял ли пользователь заказ в последние 20 минут
    if user_id in user_last_order_time:
        last_order_time = user_last_order_time[user_id]
        time_passed = current_time - last_order_time
        
        # Если прошло менее 20 минут (1200 секунд)
        if time_passed < 1200:
            # Вычисляем, сколько минут осталось ждать
            minutes_left = int((1200 - time_passed) / 60) + 1
            
            await message.answer(
                f"Вы уже отправляли заказ недавно. Пожалуйста, подождите еще {minutes_left} минут перед отправкой нового заказа.",
                reply_markup=create_main_menu(user_id)
            )
            return
    
    # Если прошло достаточно времени или это первый заказ, разрешаем отправку
    await state.set_state(States.WAITING_FOR_ORDER_DESCRIPTION)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена")
    
    await message.answer(
        "Пожалуйста, опишите, какую аватарку вы хотели бы получить:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Обработчик кнопки "Пригласить друга"
@dp.message(F.text == "Пригласить друга")
async def invite_friend(message: types.Message):
    user_id = message.from_user.id
    
    # Отправляем сообщение с фото
    try:
        from aiogram.types import FSInputFile
        photo = FSInputFile('invite.jpg')
        
        await message.answer_photo(
            photo=photo, 
            caption="Пригласите друга в Chappos Design!\n\nПоделитесь ссылкой: https://t.me/chapposdesignbot",
            reply_markup=create_main_menu(user_id)
        )
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")
        await message.answer(
            "Пригласите друга в Chappos Design!\n\nПоделитесь ссылкой: https://t.me/chapposdesignbot",
            reply_markup=create_main_menu(user_id)
        )

# Обработчик кнопки "Тех. поддержка"
@dp.message(F.text == "Тех. поддержка")
async def support(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.set_state(States.WAITING_FOR_SUPPORT_MESSAGE)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена")
    
    # Отправляем сообщение с фото
    try:
        # Исправленный способ отправки фото
        with open('support.jpg', 'rb') as file:
            # Используем FSInputFile вместо прямой передачи файла
            from aiogram.types import FSInputFile
            photo = FSInputFile('support.jpg')
            
            await message.answer_photo(
                photo=photo,
                caption="Техническая поддержка Chappos Design.\n\nОпишите вашу проблему или вопрос, и мы ответим вам в ближайшее время:",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")
        await message.answer(
            "Техническая поддержка Chappos Design.\n\nОпишите вашу проблему или вопрос, и мы ответим вам в ближайшее время:",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

# Обработчик кнопки "Заказы" (только для владельца)
@dp.message(F.text == "Заказы", F.from_user.id == OWNER_ID)
async def owner_orders(message: types.Message):
    if not active_orders:
        await message.answer("У вас нет активных заказов.", reply_markup=create_main_menu(OWNER_ID))
        return
    
    builder = InlineKeyboardBuilder()
    
    for order_id, order_info in active_orders.items():
        username = order_info['username']
        builder.button(text=f"Заказ от @{username}", callback_data=f"order_{order_id}")
    
    builder.adjust(1)
    await message.answer("Список активных заказов:", reply_markup=builder.as_markup())

# Обработчик кнопки "Отмена"
@dp.message(F.text == "Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.set_state(States.IDLE)
    
    await message.answer(
        "Действие отменено. Выберите пункт меню:",
        reply_markup=create_main_menu(user_id)
    )

# Обработчик описания заказа
@dp.message(lambda message: True, States.WAITING_FOR_ORDER_DESCRIPTION)
async def process_order_description(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    description = message.text
    
    # Сохраняем описание заказа
    user_orders[user_id] = {
        'description': description,
        'username': message.from_user.username or f"user_{user_id}"
    }
    
    await state.set_state(States.WAITING_FOR_PRICE)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена")
    
    await message.answer(
        "Укажите желаемую цену (количество звезд от 1):",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Обработчик цены заказа
@dp.message(lambda message: True, States.WAITING_FOR_PRICE)
async def process_order_price(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        price = int(message.text)
        if price < 1:
            raise ValueError("Цена должна быть положительным числом")
        
        # Сохраняем цену заказа
        user_orders[user_id]['price'] = price
        
        # Генерируем уникальный ID заказа
        order_id = f"{user_id}_{len(active_orders) + 1}"
        active_orders[order_id] = user_orders[user_id]
        
        # Отправляем уведомление владельцу
        username = user_orders[user_id]['username']
        description = user_orders[user_id]['description']
        
        builder = InlineKeyboardBuilder()
        builder.button(text="Принять", callback_data=f"accept_{order_id}")
        builder.button(text="Отклонить", callback_data=f"reject_{order_id}")
        
        await bot.send_message(
            OWNER_ID,
            f"Новый заказ от @{username}!\n\nОписание: {description}\nЦена: {price} звезд",
            reply_markup=builder.as_markup()
        )
        
        # Отправляем сообщение пользователю
        await state.set_state(States.IDLE)
        
        # Сохраняем время отправки заказа
        user_last_order_time[user_id] = time.time()
        
        await message.answer(
            "Ваш заказ отправлен! Ожидайте ответа от дизайнера.",
            reply_markup=create_main_menu(user_id)
        )
        
    except ValueError:
        builder = ReplyKeyboardBuilder()
        builder.button(text="Отмена")
        
        await message.answer(
            "Пожалуйста, введите корректное число (целое положительное число).",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

# Обработчик сообщений для тех. поддержки
@dp.message(lambda message: True, States.WAITING_FOR_SUPPORT_MESSAGE)
async def process_support_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    support_message = message.text
    username = message.from_user.username or f"user_{user_id}"
    
    # Отправляем сообщение владельцу
    builder = InlineKeyboardBuilder()
    builder.button(text="Ответить", callback_data=f"reply_{user_id}")
    
    await bot.send_message(
        OWNER_ID,
        f"Сообщение в тех. поддержку от @{username}:\n\n{support_message}",
        reply_markup=builder.as_markup()
    )
    
    # Отправляем подтверждение пользователю
    await state.set_state(States.IDLE)
    
    await message.answer(
        "Ваше сообщение отправлено в техническую поддержку. Ожидайте ответа.",
        reply_markup=create_main_menu(user_id)
    )

# Обработчик ответа владельца для тех. поддержки
@dp.message(lambda message: True, States.WAITING_FOR_OWNER_RESPONSE)
async def process_owner_response(message: types.Message, state: FSMContext):
    owner_response = message.text
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get("reply_to_user_id")
    
    if not user_id:
        await message.answer(
            "Произошла ошибка. Попробуйте ответить на сообщение снова.",
            reply_markup=create_main_menu(OWNER_ID)
        )
        return
    
    # Отправляем ответ пользователю
    try:
        await bot.send_message(
            user_id,
            f"Ответ от технической поддержки:\n\n{owner_response}"
        )
        
        # Сбрасываем состояние владельца
        await state.set_state(States.IDLE)
        await state.clear_data()
        
        await message.answer(
            "Ваш ответ отправлен пользователю.",
            reply_markup=create_main_menu(OWNER_ID)
        )
    except Exception as e:
        await message.answer(
            f"Ошибка при отправке ответа: {str(e)}",
            reply_markup=create_main_menu(OWNER_ID)
        )

# Обработчик фотографий от владельца
@dp.message(F.photo, States.WAITING_FOR_PHOTO)
async def process_owner_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]  # Берем фото с наилучшим качеством
    file_id = photo.file_id
    
    # Получаем данные из состояния
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if not order_id:
        await message.answer(
            "Произошла ошибка. Попробуйте отправить фото снова.",
            reply_markup=create_main_menu(OWNER_ID)
        )
        return
    
    # Получаем ID пользователя из order_id
    user_id = int(order_id.split('_')[0])
    
    # Отправляем фото пользователю
    try:
        await bot.send_photo(
            user_id,
            file_id,
            caption="Ваш заказ готов! Спасибо за использование Chappos Design!"
        )
        
        # Удаляем заказ из активных
        if order_id in active_orders:
            del active_orders[order_id]
        
        # Сбрасываем состояние владельца
        await state.set_state(States.IDLE)
        await state.clear_data()
        
        await message.answer(
            "Фотография отправлена пользователю. Заказ завершен.",
            reply_markup=create_main_menu(OWNER_ID)
        )
    except Exception as e:
        await message.answer(
            f"Ошибка при отправке фото: {str(e)}",
            reply_markup=create_main_menu(OWNER_ID)
        )

# Обработчик callback-запросов (для inline-кнопок)
@dp.callback_query()
async def handle_callback(call: types.CallbackQuery, state: FSMContext):
    if call.data.startswith("accept_"):
        # Принятие заказа
        order_id = call.data.split("_", 1)[1]
        user_id = int(order_id.split("_")[0])
        price = active_orders[order_id]['price']
        username = active_orders[order_id]['username']
        
        # Сохраняем информацию о платеже
        pending_payments[user_id] = {
            'order_id': order_id,
            'price': price,
            'username': username
        }
        
        # Устанавливаем состояние ожидания оплаты
        user_states_dict[user_id] = States.WAITING_FOR_PAYMENT
        
        try:
            # Создаем счет на оплату звездами
            prices = [LabeledPrice(label="XTR", amount=price)]
            
            # Отправляем счет
            await bot.send_invoice(
                chat_id=user_id,
                title=f"Оплата заказа #{order_id}",
                description=f"Оплата дизайна аватарки в Chappos Design",
                provider_token="",  # Пустой токен для звезд
                currency="XTR",     # Валюта - звезды
                prices=prices,
                start_parameter=f"order_{order_id}",
                payload=f"order_{order_id}",
                reply_markup=payment_keyboard()
            )
            
        except Exception as e:
            print(f"Ошибка при создании платежа: {e}")
            
            # Если возникла ошибка, отправляем инструкции по ручной оплате
            payment_message = f"""
Ваш заказ принят дизайнером!

Информация о заказе:
- Номер заказа: #{order_id}
- Сумма к оплате: {price} звезд

Для оплаты:
1. Отправьте {price} звезд в этот чат
2. После отправки нажмите кнопку ниже
"""
            
            # Создаем кнопку для подтверждения оплаты
            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Я уже отправил звезды", callback_data="paid")
            
            await bot.send_message(
                user_id,
                payment_message,
                reply_markup=builder.as_markup()
            )
        
        # Обновляем сообщение владельца
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\nСтатус: Принят ✅",
            reply_markup=None
        )
        
        await call.answer()
        
    elif call.data == "paid":
        # Пользователь подтверждает, что отправил звезды
        user_id = call.from_user.id
        
        # Проверяем, что пользователь ожидал оплаты
        if user_id not in pending_payments:
            await call.answer("Ошибка: заказ не найден или уже оплачен.", show_alert=True)
            return
        
        order_id = pending_payments[user_id]['order_id']
        price = pending_payments[user_id]['price']
        username = pending_payments[user_id]['username']
        
        # Уведомляем владельца о необходимости проверить оплату
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data=f"confirm_{order_id}")
        builder.button(text="❌ Отклонить", callback_data=f"reject_payment_{order_id}")
        
        await bot.send_message(
            OWNER_ID,
            f"Пользователь @{username} утверждает, что отправил {price} звезд за заказ #{order_id}.\n\nПожалуйста, проверьте получение звезд и подтвердите или отклоните оплату.",
            reply_markup=builder.as_markup()
        )
        
        # Уведомляем пользователя
        await call.answer("Спасибо! Ваша оплата передана на проверку. Пожалуйста, ожидайте подтверждения.", show_alert=True)
        
        # Обновляем сообщение
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\nСтатус: Ожидает подтверждения оплаты ⏳",
            reply_markup=None
        )
        
    elif call.data.startswith("confirm_"):
        # Владелец подтверждает оплату
        order_id = call.data.split("_", 1)[1]
        user_id = int(order_id.split("_")[0])
        
        # Проверяем, что заказ существует
        if order_id not in active_orders:
            await call.answer("Заказ не найден.", show_alert=True)
            return
        
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            f"Ваша оплата заказа #{order_id} подтверждена! Дизайнер приступает к выполнению заказа.",
            reply_markup=create_main_menu(user_id)
        )
        
        # Уведомляем владельца
        await call.answer("Оплата подтверждена!")
        
        # Обновляем сообщение владельца
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\nСтатус: Оплата подтверждена ✅",
            reply_markup=None
        )
        
        # Сбрасываем состояние пользователя
        user_states_dict[user_id] = States.IDLE
        
        # Удаляем из ожидающих оплату
        if user_id in pending_payments:
            del pending_payments[user_id]
            
    elif call.data.startswith("reject_payment_"):
        # Владелец отклоняет оплату
        order_id = call.data.split("_", 2)[2]
        user_id = int(order_id.split("_")[0])
        
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            f"К сожалению, ваша оплата заказа #{order_id} не была подтверждена. Пожалуйста, свяжитесь с технической поддержкой для уточнения деталей.",
            reply_markup=create_main_menu(user_id)
        )
        
        # Уведомляем владельца
        await call.answer("Оплата отклонена!")
        
        # Обновляем сообщение владельца
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\nСтатус: Оплата отклонена ❌",
            reply_markup=None
        )
        
        # Сбрасываем состояние пользователя
        user_states_dict[user_id] = States.IDLE
        
        # Удаляем из ожидающих оплату
        if user_id in pending_payments:
            del pending_payments[user_id]
            
    elif call.data.startswith("reply_"):
        # Ответ на сообщение в тех. поддержку
        user_id = int(call.data.split("_", 1)[1])
        
        # Устанавливаем состояние владельца
        await state.set_state(States.WAITING_FOR_OWNER_RESPONSE)
        await state.update_data(reply_to_user_id=user_id)
        
        builder = ReplyKeyboardBuilder()
        builder.button(text="Отмена")
        
        await bot.send_message(
            OWNER_ID,
            "Введите ваш ответ пользователю:",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        
        await call.answer()
        
    elif call.data.startswith("order_"):
        # Просмотр заказа владельцем
        order_id = call.data.split("_", 1)[1]
        
        # Устанавливаем состояние владельца
        await state.set_state(States.WAITING_FOR_PHOTO)
        await state.update_data(order_id=order_id)
        
        builder = ReplyKeyboardBuilder()
        builder.button(text="Отмена")
        
        await bot.send_message(
            OWNER_ID,
            "Отправьте фотографию готовой аватарки для пользователя:",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        
        await call.answer()

# Обработчик предварительной проверки платежа
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    try:
        # Всегда принимаем платеж
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        print(f"Ошибка при обработке pre_checkout_query: {e}")

# Обработчик успешного платежа
@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        payload = message.successful_payment.invoice_payload
        
        # Извлекаем ID заказа из payload
        order_id = payload.split("_", 1)[1]
        
        # Проверяем, существует ли заказ
        if order_id not in active_orders:
            await message.answer("Ошибка: заказ не найден.", reply_markup=create_main_menu(user_id))
            return
        
        price = active_orders[order_id]['price']
        username = active_orders[order_id]['username']
        
        # Создаем сообщение с подтверждением оплаты
        confirmation_message = f"""
💳 Подтверждение оплаты 💳

Заказ: #{order_id}
Сумма: {price} звезд

Оплата прошла успешно! Дизайнер приступает к выполнению заказа.
"""
        
        # Отправляем подтверждение пользователю
        await message.answer(
            confirmation_message,
            reply_markup=create_main_menu(user_id)
        )
        
        # Уведомляем владельца
        await bot.send_message(
            OWNER_ID,
            f"Пользователь @{username} оплатил заказ #{order_id} через платежную систему ({price} звезд). Можете приступать к выполнению."
        )
        
        # Сбрасываем состояние пользователя
        user_states_dict[user_id] = States.IDLE
        
        # Удаляем из ожидающих оплату
        if user_id in pending_payments:
            del pending_payments[user_id]
            
    except Exception as e:
        print(f"Ошибка при обработке успешного платежа: {e}")
        await message.answer("Произошла ошибка при обработке платежа. Пожалуйста, свяжитесь с технической поддержкой.")

# Функция для проверки и удаления просроченных заказов
async def check_expired_orders():
    while True:
        current_time = time.time()
        expired_orders = []
        
        # Проверяем все ожидающие оплаты заказы
        for user_id, payment_info in pending_payments.items():
            # Если прошло более 20 минут (1200 секунд)
            if current_time - payment_info.get('timestamp', 0) > 1200:
                expired_orders.append(user_id)
                order_id = payment_info['order_id']
                
                # Уведомляем пользователя
                try:
                    await bot.send_message(
                        user_id,
                        f"Время ожидания оплаты для заказа #{order_id} истекло. Заказ отменен.",
                        reply_markup=create_main_menu(user_id)
                    )
                    
                    # Сбрасываем состояние пользователя
                    user_states_dict[user_id] = States.IDLE
                    
                    # Уведомляем владельца
                    await bot.send_message(
                        OWNER_ID,
                        f"Заказ #{order_id} от @{payment_info['username']} отменен из-за истечения времени ожидания оплаты."
                    )
                except Exception as e:
                    print(f"Ошибка при обработке истекшего заказа: {e}")
        
        # Удаляем просроченные заказы
        for user_id in expired_orders:
            if user_id in pending_payments:
                order_id = pending_payments[user_id]['order_id']
                del pending_payments[user_id]
                
                # Удаляем заказ из активных, если он там еще есть
                if order_id in active_orders:
                    del active_orders[order_id]
        
        # Проверяем каждые 60 секунд
        await asyncio.sleep(60)

# Обработчик отклонения заказа
@dp.callback_query(lambda call: call.data.startswith("reject_"))
async def handle_reject(call: types.CallbackQuery):
    order_id = call.data.split("_", 1)[1]
    user_id = int(order_id.split("_")[0])
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        "К сожалению, ваш заказ был отклонен. Вы можете отправить новый заказ.",
        reply_markup=create_main_menu(user_id)
    )
    
    # Удаляем запись о времени последнего заказа, чтобы пользователь мог сразу отправить новый
    if user_id in user_last_order_time:
        del user_last_order_time[user_id]
    
    # Удаляем заказ из активных
    if order_id in active_orders:
        del active_orders[order_id]
    
    # Обновляем сообщение владельца
    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"{call.message.text}\n\nСтатус: Отклонен ❌",
        reply_markup=None
    )
    
    await call.answer("Заказ отклонен")

# Запуск бота
async def main():
    # Создаем необходимые файлы, если их нет
    required_files = ['welcome.jpg', 'invite.jpg', 'support.jpg']
    for file in required_files:
        if not os.path.exists(file):
            # Создаем пустой файл, чтобы избежать ошибок
            # В реальном проекте замените на настоящие изображения
            with open(file, 'w') as f:
                f.write('')
    
    # Запускаем задачу проверки просроченных заказов
    asyncio.create_task(check_expired_orders())
    
    # Запускаем бота
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
