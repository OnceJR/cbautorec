import subprocess
import time
import os
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
    process = recording_processes.get(chat_id)
    if process and process.poll() is None:
        process.terminate()
        del recording_processes[chat_id]
        return True
    return False

async def generar_thumbnail(video_path):
    thumbnail_path = f'{os.path.splitext(video_path)[0]}_thumbnail.jpg'
    try:
        subprocess.run([
            'ffmpeg',
            '-i', video_path,
            '-vf', 'thumbnail,scale=320:240',
            '-frames:v', '1',
            thumbnail_path
        ], check=True)
        return thumbnail_path
    except subprocess.CalledProcessError as e:
        print(f"Error al generar el thumbnail: {e}")
        return None

async def grabar_completo(url, output_file):
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-movflags', '+faststart',
        output_file
    ]

    process = subprocess.Popen(command_ffmpeg)
    return process

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    duration = 30

    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-movflags', '+faststart',
        output_file
    ]

    try:
        subprocess.run(command_ffmpeg, check=True)
        thumbnail_path = await generar_thumbnail(output_file)
        return output_file, thumbnail_path
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None, None

async def upload_video(chat_id, file_path, thumbnail_path=None):
    file_parts = dividir_archivo(file_path) if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024 else [file_path]

    for part in file_parts:
        try:
            await bot.send_file(chat_id, part, supports_streaming=True, thumb=thumbnail_path)
            os.remove(part)
        except Exception as e:
            print(f"Error al enviar el archivo: {e}")

@bot.on(events.NewMessage(pattern='/grabar_clip'))
async def handle_grabar_clip(event):
    await event.respond("Por favor, envía la URL de la transmisión para grabar un clip.")

@bot.on(events.NewMessage(pattern='/grabar_completo'))
async def handle_grabar_completo(event):
    await event.respond("Por favor, envía la URL de la transmisión para grabar la transmisión completa.")

@bot.on(events.NewMessage(pattern='/detener'))
async def handle_detener(event):
    if detener_grabacion(event.chat_id):
        await event.respond("Grabación detenida. Generando thumbnail y subiendo el archivo...")
        output_file = f'completo_{event.chat_id}.mp4'
        thumbnail = await generar_thumbnail(output_file)
        await upload_video(event.chat_id, output_file, thumbnail)
    else:
        await event.respond("No hay grabación en curso.")

@bot.on(events.NewMessage)
async def process_url(event):
    url = event.raw_text
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
    calidad = event.data.decode('utf-8')
    chat_id = event.chat_id
    flujo_url = user_data.get(chat_id)

    if calidad.startswith('clip'):
        await event.edit("Grabando clip...")
        calidad_clip = calidad.split('_')[1]
        clip_path, thumbnail_path = await grabar_clip(flujo_url, calidad_clip)
        if clip_path and thumbnail_path:
            await upload_video(chat_id, clip_path, thumbnail_path)
        else:
            await event.respond("No se pudo grabar el clip.")
    elif calidad == 'completo':
        await event.edit("Grabando transmisión completa...")
        output_file = f'completo_{chat_id}.mp4'
        process = await grabar_completo(flujo_url, output_file)
        recording_processes[chat_id] = process

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "¡Hola! Aquí están los comandos disponibles:\n"
        "/grabar_clip - Graba un clip de 30 segundos.\n"
        "/grabar_completo - Graba la transmisión completa.\n"
        "/detener - Detiene la grabación en curso."
    )

bot.start()
bot.run_until_disconnected()
