import re
import subprocess
import time
import os
from telethon import TelegramClient, events, Button

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Diccionario para almacenar datos de los usuarios
user_data = {}

# Expresión regular para validar URLs
url_pattern = re.compile(
    r'^(https?://)?(www\.)?([a-zA-Z0-9-]+)\.[a-zA-Z]{2,6}(/[\w-./?%&=]*)?$'
)

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    thumbnail_file = f'thumbnail_{time.strftime("%Y%m%d_%H%M%S")}.jpg'
    duration = 30

    # Comando para grabar la transmisión con FFmpeg
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'libx264',  # Usar codec H.264 para mayor compatibilidad
        '-preset', 'fast',  # Ajuste de velocidad para procesamiento rápido
        '-crf', '23',  # Calidad del video (ajustable)
        '-c:a', 'aac',  # Codificación de audio
        '-movflags', '+faststart',  # Habilita el inicio rápido para streaming
        output_file
    ]

    try:
        # Ejecuta el comando de grabación
        subprocess.run(command_ffmpeg, check=True)
        
        # Extrae el primer fotograma como thumbnail
        subprocess.run([
            'ffmpeg',
            '-i', output_file,
            '-vf', 'thumbnail,scale=320:240',
            '-frames:v', '1',
            thumbnail_file
        ], check=True)
        
        return output_file, thumbnail_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None, None

async def upload_video(chat_id, clip_path, thumbnail_path):
    try:
        # Envía el video con el thumbnail extraído, habilitando supports_streaming=True
        await bot.send_file(
            chat_id,
            clip_path,
            thumb=thumbnail_path,
            supports_streaming=True  # Habilita la reproducción en streaming
        )
        os.remove(clip_path)  # Limpieza de archivos después del envío
        os.remove(thumbnail_path)
    except Exception as e:
        print(f"Error al enviar el video: {e}")

@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond("Por favor, envía la URL de la transmisión.")

@bot.on(events.NewMessage)
async def process_url(event):
    url = event.raw_text.strip()
    if re.match(url_pattern, url):
        # Si el mensaje coincide con el patrón de URL, procedemos
        user_data[event.chat_id] = url
        await event.respond(
            "Selecciona la calidad para grabar:",
            buttons=[
                [Button.inline("Alta", b'alta'), Button.inline("Media", b'media'), Button.inline("Baja", b'baja')]
            ]
        )
    else:
        # Si el mensaje no es una URL válida, informamos al usuario
        await event.respond("Por favor, envía un enlace de transmisión válido.")

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    quality = event.data.decode('utf-8')
    flujo_url = user_data.get(event.chat_id)
    
    if not flujo_url:
        await event.respond("No se encontró un enlace válido.")
        return
    
    await event.edit("Grabando clip...")
    clip_path, thumbnail_path = await grabar_clip(flujo_url, quality)
    
    if clip_path and thumbnail_path:
        await upload_video(event.chat_id, clip_path, thumbnail_path)
    else:
        await event.respond("No se pudo grabar el clip.")

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión."
    )
    await event.respond(welcome_message)

bot.start()
bot.run_until_disconnected()
