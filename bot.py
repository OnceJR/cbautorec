import subprocess
import time
import os
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.utils import executor

# Configuración de la API
API_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"

# Inicialización del bot y el despachador
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Diccionario para almacenar datos de los usuarios
user_data = {}

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    duration = 30  # Duración fija a 30 segundos

    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_file
    ]

    try:
        subprocess.run(command_ffmpeg, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

async def upload_video(chat_id, clip_path):
    with open(clip_path, "rb") as video_file:
        await bot.send_video(chat_id, video_file, supports_streaming=True)
        os.remove(clip_path)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await message.reply(welcome_message)

@dp.message_handler(commands=['grabar'])
async def handle_grabar(message: types.Message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@dp.message_handler(F.text & ~F.command())
async def process_url(message: types.Message):
    url = message.text
    await message.reply("Obteniendo enlace de transmisión...")

    buttons = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("Alta", callback_data="alta"),
         types.InlineKeyboardButton("Media", callback_data="media"),
         types.InlineKeyboardButton("Baja", callback_data="baja")]
    ])
    
    await message.reply("Selecciona la calidad para grabar:", reply_markup=buttons)
    user_data[message.chat.id] = url

@dp.callback_query_handler()
async def handle_quality_selection(callback_query: types.CallbackQuery):
    quality = callback_query.data
    await callback_query.answer()

    flujo_url = user_data.get(callback_query.message.chat.id)
    if not flujo_url:
        await callback_query.message.reply("No se encontró un enlace válido.")
        return

    await callback_query.message.edit_text("Grabando clip...")
    clip_path = await grabar_clip(flujo_url, quality)

    if clip_path:
        await upload_video(callback_query.message.chat.id, clip_path)
    else:
        await callback_query.message.reply("No se pudo grabar el clip.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
