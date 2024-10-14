import subprocess
import time
import os
from telethon import TelegramClient, events, Button
from threading import Thread

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Diccionario para almacenar datos de los usuarios y grabaciones en curso
user_data = {}
active_recordings = {}

async def grabar_clip(url, quality, duration=30):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    thumbnail_file = f'thumbnail_{time.strftime("%Y%m%d_%H%M%S")}.jpg'

    # Comando para grabar la transmisión con FFmpeg
    command_ffmpeg = [
        'ffmpeg', '-i', url, '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-movflags', '+faststart',
        output_file
    ]

    try:
        # Ejecuta el comando de grabación
        subprocess.run(command_ffmpeg, check=True)

        # Extrae el primer fotograma como thumbnail
        subprocess.run([
            'ffmpeg', '-i', output_file, '-vf', 'thumbnail,scale=320:240',
            '-frames:v', '1', thumbnail_file
        ], check=True)

        return output_file, thumbnail_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None, None

async def grabar_completo(url, chat_id):
    output_file = f'full_stream_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
    
    # Comando para grabar la transmisión completa con FFmpeg
    command_ffmpeg = [
        'ffmpeg', '-i', url, '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart',
        output_file
    ]

    # Almacena el proceso activo
    process = subprocess.Popen(command_ffmpeg)
    active_recordings[chat_id] = process
    print(f"Grabación iniciada para {chat_id}")

    process.wait()
    print(f"Grabación completa para {chat_id}")

    # Elimina el proceso de las grabaciones activas
    del active_recordings[chat_id]
    return output_file

async def detener_grabacion(chat_id):
    process = active_recordings.get(chat_id)
    if process:
        process.terminate()  # Detiene el proceso de grabación
        process.wait()  # Espera a que termine el proceso
        del active_recordings[chat_id]
        return True
    return False

async def upload_video(chat_id, clip_path, thumbnail_path=None):
    try:
        # Envía el video con el thumbnail extraído, si está disponible
        await bot.send_file(
            chat_id,
            clip_path,
            thumb=thumbnail_path,
            supports_streaming=True
        )
        os.remove(clip_path)
        if thumbnail_path:
            os.remove(thumbnail_path)
    except Exception as e:
        print(f"Error al enviar el video: {e}")

@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond("Por favor, envía la URL de la transmisión.")

@bot.on(events.NewMessage(pattern='/grabar_completo'))
async def handle_grabar_completo(event):
    await event.respond("Por favor, envía la URL de la transmisión para grabar completa.")

@bot.on(events.NewMessage(pattern='/detener'))
async def handle_detener(event):
    chat_id = event.chat_id
    if await detener_grabacion(chat_id):
        await event.respond("Grabación detenida con éxito.")
    else:
        await event.respond("No se encontró una grabación en curso.")

@bot.on(events.NewMessage)
async def process_url(event):
    url = event.raw_text
    if url.startswith("http"):
        user_data[event.chat_id] = url
        await event.respond(
            "Selecciona la calidad para grabar:",
            buttons=[
                [Button.inline("Alta", b'alta'), Button.inline("Media", b'media'), Button.inline("Baja", b'baja')],
                [Button.inline("Completa", b'completa')]
            ]
        )
    else:
        await event.respond("Por favor, envía un enlace de transmisión válido.")

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    quality = event.data.decode('utf-8')
    flujo_url = user_data.get(event.chat_id)

    if not flujo_url:
        await event.respond("No se encontró un enlace válido.")
        return

    if quality == 'completa':
        await event.edit("Iniciando grabación completa...")
        Thread(target=asyncio.run, args=(grabar_completo(flujo_url, event.chat_id),)).start()
    else:
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
        "Comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos.\n"
        "/grabar_completo - Inicia la grabación de una transmisión completa.\n"
        "/detener - Detiene la grabación completa."
    )
    await event.respond(welcome_message)

bot.start()
bot.run_until_disconnected()
