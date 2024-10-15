import os
import time
import asyncio
import aiofiles
from telethon import TelegramClient, events, Button

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Diccionario para almacenar datos de los usuarios y procesos de grabación
user_data = {}
recording_processes = {}

def dividir_archivo(file_path, max_size=2 * 1024 * 1024 * 1024):  # 2 GB
    """Divide un archivo en partes más pequeñas si excede el tamaño especificado."""
    file_parts = []
    file_size = os.path.getsize(file_path)
    part_num = 1

    with open(file_path, 'rb') as f:
        while f.tell() < file_size:
            part_path = f"{file_path}_part{part_num}.mp4"
            with open(part_path, 'wb') as part_file:
                part_file.write(f.read(max_size))
            file_parts.append(part_path)
            part_num += 1

    return file_parts

def detener_grabacion(chat_id):
    """Detiene un proceso de grabación en curso."""
    process = recording_processes.get(chat_id)
    if process and process.returncode is None:
        process.terminate()
        del recording_processes[chat_id]
        return True
    return False

async def grabar_completo(url, output_file):
    """Graba la transmisión completa en el archivo especificado usando FFmpeg."""
    command_ffmpeg = [
        'ffmpeg', '-i', url, '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart', output_file
    ]

    try:
        process = await asyncio.create_subprocess_exec(*command_ffmpeg)
        return process
    except Exception as e:
        print(f"Error al iniciar la grabación completa: {e}")
        return None

async def grabar_clip(url, quality):
    """Graba un clip de 30 segundos y genera una miniatura."""
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    thumbnail_file = f'thumbnail_{time.strftime("%Y%m%d_%H%M%S")}.jpg'
    duration = 30

    command_ffmpeg = [
        'ffmpeg', '-i', url, '-t', str(duration), '-c:v', 'libx264',
        '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart', output_file
    ]

    try:
        await asyncio.create_subprocess_exec(*command_ffmpeg)
        await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', output_file, '-vf', 'thumbnail,scale=320:240', 
            '-frames:v', '1', thumbnail_file
        )
        return output_file, thumbnail_file
    except Exception as e:
        print(f"Error al grabar el clip: {e}")
        return None, None

async def upload_video(chat_id, file_path):
    """Sube el archivo (o sus partes) al chat de Telegram."""
    file_parts = dividir_archivo(file_path) if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024 else [file_path]

    for part in file_parts:
        try:
            await bot.send_file(chat_id, part, supports_streaming=True)
            os.remove(part)  # Elimina la parte del archivo después de enviarla
        except Exception as e:
            print(f"Error al enviar el archivo: {e}")

@bot.on(events.NewMessage(pattern='/grabar_clip'))
async def handle_grabar_clip(event):
    """Inicia la grabación de un clip."""
    await event.respond("Por favor, envía la URL de la transmisión para grabar un clip.")

@bot.on(events.NewMessage(pattern='/grabar_completo'))
async def handle_grabar_completo(event):
    """Inicia la grabación completa de una transmisión."""
    await event.respond("Por favor, envía la URL de la transmisión para grabar la transmisión completa.")

@bot.on(events.NewMessage(pattern='/detener'))
async def handle_detener(event):
    """Detiene la grabación en curso y sube el archivo grabado."""
    if detener_grabacion(event.chat_id):
        await event.respond("Grabación detenida. Subiendo el archivo...")
        await upload_video(event.chat_id, f'completo_{event.chat_id}.mp4')
    else:
        await event.respond("No hay grabación en curso.")

@bot.on(events.NewMessage)
async def process_url(event):
    """Procesa la URL de la transmisión y ofrece opciones de grabación."""
    url = event.raw_text.strip()
    chat_id = event.chat_id

    if url.startswith("http"):
        user_data[chat_id] = url
        if chat_id in recording_processes:
            await event.respond("Ya hay una grabación en curso. Usa /detener para finalizarla.")
        else:
            await event.respond(
                "Selecciona la calidad o tipo de grabación:",
                buttons=[
                    [Button.inline("Clip Alta", b'clip_alta'), Button.inline("Clip Media", b'clip_media')],
                    [Button.inline("Completo", b'completo')]
                ]
            )
    else:
        await event.respond("Por favor, envía un enlace de transmisión válido.")

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    """Maneja la selección de calidad o tipo de grabación."""
    calidad = event.data.decode('utf-8')
    chat_id = event.chat_id
    flujo_url = user_data.get(chat_id)

    if not flujo_url:
        await event.respond("No se encontró un enlace válido.")
        return

    if calidad.startswith('clip'):
        await event.edit("Grabando clip...")
        calidad_clip = calidad.split('_')[1]
        clip_path, thumbnail_path = await grabar_clip(flujo_url, calidad_clip)
        if clip_path:
            await upload_video(chat_id, clip_path)
        else:
            await event.respond("No se pudo grabar el clip.")
    elif calidad == 'completo':
        await event.edit("Grabando transmisión completa...")
        output_file = f'completo_{chat_id}.mp4'
        process = await grabar_completo(flujo_url, output_file)
        if process:
            recording_processes[chat_id] = process

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    """Envía un mensaje de bienvenida con los comandos disponibles."""
    await event.respond(
        "¡Hola! Aquí están los comandos disponibles:\n"
        "/grabar_clip - Graba un clip de 30 segundos.\n"
        "/grabar_completo - Graba la transmisión completa.\n"
        "/detener - Detiene la grabación en curso."
    )

try:
    bot.start()
    bot.run_until_disconnected()
except Exception as e:
    print(f"Error al iniciar el bot: {e}")
