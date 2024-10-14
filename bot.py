import subprocess
import time
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Diccionario para almacenar URLs por chat_id
url_storage = {}

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'  # Nombre del clip
    duration = 30  # Duración fija a 30 segundos

    # Comando para grabar la transmisión usando FFmpeg
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),  # Duración fija a 30 segundos
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-movflags', '+faststart',  # Para mejor presentación en la web
        '-vf', 'thumbnail',  # Crea un thumbnail a partir del video
        output_file
    ]

    try:
        subprocess.run(command_ffmpeg, check=True)  # Ejecuta el comando de grabación
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on_message(filters.text & ~filters.command("start"))  # Solo procesar texto que no es el comando /start
async def process_url(client, message):
    url = message.text
    url_storage[message.chat.id] = url  # Almacena la URL en el diccionario

    await message.reply("Obteniendo enlace de transmisión...")

    flujo_url = url  # Aquí se debe obtener el enlace real de transmisión

    # Botones para seleccionar calidad
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Alta", callback_data="alta"),
            InlineKeyboardButton("Media", callback_data="media"),
            InlineKeyboardButton("Baja", callback_data="baja"),
        ]
    ])
    
    await message.reply("Selecciona la calidad para grabar:", reply_markup=buttons)

@bot.on_callback_query(filters.regex('^(alta|media|baja)$'))
async def handle_quality_selection(client, callback_query):
    quality = callback_query.data
    flujo_url = url_storage.get(callback_query.message.chat.id)  # Recupera la URL del diccionario
    await callback_query.answer()  # Acknowledge the callback query

    if flujo_url:
        await callback_query.message.reply("Grabando clip...")
        clip_path = await grabar_clip(flujo_url, quality)  # Graba el clip

        if clip_path:
            with open(clip_path, 'rb') as video_file:
                await bot.send_video(callback_query.message.chat.id, video_file)
            os.remove(clip_path)  # Elimina el clip después de enviarlo
        else:
            await callback_query.message.reply("No se pudo grabar el clip.")
    else:
        await callback_query.message.reply("URL no encontrada. Por favor, envía una URL válida.")

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
