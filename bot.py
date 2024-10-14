import os
import time
import subprocess
from telethon import TelegramClient, events
from telethon import Button

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

# Inicializa el cliente de Telethon
client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

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
        await client.send_file(chat_id, video_file, supports_streaming=True)
        os.remove(clip_path)

@client.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await event.respond(welcome_message)

@client.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond("Por favor, envía la URL de la transmisión de Chaturbate.")

@client.on(events.NewMessage())
async def process_url(event):
    url = event.message.message
    await event.respond("Obteniendo enlace de transmisión...")

    # Crear botones para seleccionar calidad
    buttons = [
        [Button.inline("Alta", b"alta"), Button.inline("Media", b"media"), Button.inline("Baja", b"baja")]
    ]

    await event.respond("Selecciona la calidad para grabar:", buttons=buttons)

    # Guardar el enlace para usar más tarde
    user_data[event.chat_id] = url  # Guardar la URL en el diccionario

@client.on(events.CallbackQuery)
async def handle_quality_selection(event):
    quality = event.data.decode('utf-8')
    await event.answer()  # Responde al callback

    flujo_url = user_data.get(event.chat_id)
    if not flujo_url:
        await event.respond("No se encontró un enlace válido.")
        return

    await event.respond("Grabando clip...")

    clip_path = await grabar_clip(flujo_url, quality)

    if clip_path:
        await upload_video(event.chat_id, clip_path)
    else:
        await event.respond("No se pudo grabar el clip.")

# Ejecutar el bot
client.run_until_disconnected()
