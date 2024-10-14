import telebot
import subprocess
import time
import os
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es'
bot = Client("my_bot", bot_token=API_TOKEN)

# Almacenamiento temporal para URLs
urls = {}

async def grabar_clip(url):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'  # Nombre del clip
    duration = 30  # Duración del clip en segundos

    # Comando para grabar la transmisión usando FFmpeg
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-vf', 'thumbnail',  # Aplica un filtro de thumbnail dinámico
        '-t', str(duration),
        '-c:v', 'libx264',  # Cambia a un codec que soporte thumbnails dinámicos
        '-preset', 'fast',  # Opcional: puedes ajustar la velocidad de codificación
        output_file
    ]
    
    subprocess.run(command_ffmpeg)  # Ejecuta el comando de grabación
    return output_file

@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")
    urls[message.chat.id] = None  # Inicializa el almacenamiento de URL

@bot.on_message(filters.private)
async def process_url(client, message):
    url = message.text
    if message.chat.id in urls:
        urls[message.chat.id] = url  # Guardar la URL
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Alta", callback_data="alta"),
             InlineKeyboardButton("Media", callback_data="media"),
             InlineKeyboardButton("Baja", callback_data="baja")]
        ])
        await message.reply("Selecciona la calidad para grabar:", reply_markup=buttons)
    else:
        await message.reply("No se ha iniciado la grabación. Usa /grabar.")

@bot.on_callback_query()
async def handle_quality_selection(client, callback_query):
    quality = callback_query.data
    flujo_url = urls[callback_query.message.chat.id]  # Recupera la URL
    clip_path = await grabar_clip(flujo_url)  # Graba el clip

    # Envía el video a Telegram
    with open(clip_path, 'rb') as video_file:
        await callback_query.message.reply_video(video_file, caption="Grabación completada.")

    # Eliminar el clip después de enviarlo
    os.remove(clip_path)

@bot.on_message(filters.command('start'))
async def send_welcome(client, message):
    await message.reply("¡Hola! Usa el comando /grabar para grabar un clip de 30 segundos de una transmisión de Chaturbate.")

# Ejecutar el bot
if __name__ == '__main__':
    bot.run()
