import subprocess
import os
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    duration = 30  # Duración fija a 30 segundos

    # Comando para grabar la transmisión usando FFmpeg con calidad seleccionada
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-vf', 'thumbnail',  # Generar un thumbnail
        '-c:v', 'libx264',  # Usar libx264 para la codificación
        '-preset', 'fast',
        '-crf', '23',  # Ajusta el valor de CRF para controlar la calidad
        output_file
    ]

    subprocess.run(command_ffmpeg)
    return output_file

@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on_message(filters.text & ~filters.command("start"))
async def process_url(client, message):
    url = message.text
    await message.reply("Selecciona la calidad para grabar:", reply_markup=build_quality_buttons(url))

def build_quality_buttons(url):
    buttons = [
        [InlineKeyboardButton("Baja", callback_data=f"quality_low_{url}")],
        [InlineKeyboardButton("Media", callback_data=f"quality_medium_{url}")],
        [InlineKeyboardButton("Alta", callback_data=f"quality_high_{url}")]
    ]
    return InlineKeyboardMarkup(buttons)

@bot.on_callback_query(filters.regex(r"quality_(low|medium|high)_(.*)"))
async def handle_quality_selection(client, callback_query):
    quality = callback_query.data.split('_')[1]
    url = callback_query.data.split('_')[2]

    await callback_query.answer()  # Acknowledge the callback
    await callback_query.message.delete()  # Eliminar el mensaje anterior para mantener el chat limpio
    await callback_query.message.reply("Grabando clip...")

    clip_path = await grabar_clip(url, quality)
    await send_video_with_thumbnail(callback_query.message.chat.id, clip_path)

async def send_video_with_thumbnail(chat_id, clip_path):
    with open(clip_path, 'rb') as video_file:
        await bot.send_video(chat_id, video_file, thumb=clip_path, caption="Aquí está tu clip grabado.")
    os.remove(clip_path)  # Eliminar el clip después de enviarlo

@bot.on_message(filters.command('start'))
async def send_welcome(client, message):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await message.reply(welcome_message)

# Ejecutar el bot
if __name__ == '__main__':
    bot.run()
