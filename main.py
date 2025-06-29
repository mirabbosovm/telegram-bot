
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
import json
import os
from keep_alive import keep_alive

API_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 123456789

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

USERS_FILE = "users.json"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

class Register(StatesGroup):
    waiting_for_contact = State()
    waiting_for_name = State()

class MessageForm(StatesGroup):
    collecting_messages = State()

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    with open(USERS_FILE) as f:
        users = json.load(f)
    if str(message.from_user.id) in users:
        await show_main_menu(message)
    else:
        contact_btn = KeyboardButton("📞 Raqamni yuborish", request_contact=True)
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add(contact_btn)
        await message.answer("Botdan foydalanish uchun telefon raqamingizni yuboring:", reply_markup=markup)
        await Register.waiting_for_contact.set()

@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.waiting_for_contact)
async def get_contact(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Ismingizni kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await Register.waiting_for_name.set()

@dp.message_handler(state=Register.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data['phone']
    name = message.text

    with open(USERS_FILE) as f:
        users = json.load(f)
    users[str(message.from_user.id)] = {"name": name, "phone": phone}
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

    await message.answer(f"Ro'yxatdan o'tdingiz, {name}!", reply_markup=types.ReplyKeyboardRemove())
    await show_main_menu(message)
    await state.finish()

async def show_main_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✉️ Xabar yuborish", "📨 Javoblarim")
    await message.answer("Asosiy menyu:", reply_markup=markup)

@dp.message_handler(lambda message: message.text == "✉️ Xabar yuborish")
async def start_message_collect(message: types.Message, state: FSMContext):
    await state.update_data(messages=[])
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📤 Yuborish")
    await message.answer("Xabaringizni yuboring. Bir nechta matn, rasm, video, yoki audio yuborishingiz mumkin.
Yakunlash uchun '📤 Yuborish' tugmasini bosing.", reply_markup=markup)
    await MessageForm.collecting_messages.set()

@dp.message_handler(lambda message: message.text == "📤 Yuborish", state=MessageForm.collecting_messages)
async def send_to_admin(message: types.Message, state: FSMContext):
    data = await state.get_data()
    messages = data['messages']
    with open(USERS_FILE) as f:
        users = json.load(f)
    user_info = users.get(str(message.from_user.id), {})
    caption = f"✉️ Yangi xabar!
👤 Ism: {user_info.get('name')}
📞 Tel: {user_info.get('phone')}
🆔 ID: {message.from_user.id}"

    await bot.send_message(ADMIN_ID, caption)
    for msg in messages:
        if msg['type'] == 'text':
            await bot.send_message(ADMIN_ID, msg['content'])
        elif msg['type'] == 'photo':
            await bot.send_photo(ADMIN_ID, msg['file_id'])
        elif msg['type'] == 'video':
            await bot.send_video(ADMIN_ID, msg['file_id'])
        elif msg['type'] == 'voice':
            await bot.send_voice(ADMIN_ID, msg['file_id'])

    await message.answer("Xabaringiz yuborildi ✅", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("✉️ Xabar yuborish", "📨 Javoblarim"))
    await state.finish()

@dp.message_handler(state=MessageForm.collecting_messages, content_types=types.ContentTypes.ANY)
async def collect_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    messages = data.get('messages', [])
    if message.text:
        messages.append({'type': 'text', 'content': message.text})
    elif message.photo:
        messages.append({'type': 'photo', 'file_id': message.photo[-1].file_id})
    elif message.video:
        messages.append({'type': 'video', 'file_id': message.video.file_id})
    elif message.voice:
        messages.append({'type': 'voice', 'file_id': message.voice.file_id})
    await state.update_data(messages=messages)

@dp.message_handler(lambda message: message.text == "📨 Javoblarim")
async def show_replies(message: types.Message):
    filepath = f"replies_{message.from_user.id}.txt"
    if os.path.exists(filepath):
        with open(filepath) as f:
            content = f.read()
        await message.answer(f"🔁 Sizga yuborilgan javoblar:

{content}")
    else:
        await message.answer("Sizga hali javob yuborilmagan.")

@dp.message_handler(lambda message: message.reply_to_message, user_id=ADMIN_ID)
async def admin_reply(message: types.Message):
    try:
        lines = message.reply_to_message.text.splitlines()
        for line in lines:
            if "ID: " in line:
                user_id = int(line.split("ID: ")[-1])
                break
        else:
            await message.answer("Foydalanuvchi ID topilmadi.")
            return

        await bot.send_message(user_id, f"✉️ Yangi javob:
{message.text}")
        with open(f"replies_{user_id}.txt", "a") as f:
            f.write(f"{message.text}

")
        await message.answer("Javob yuborildi ✅")
    except Exception as e:
        await message.answer(f"Xatolik: {str(e)}")

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
