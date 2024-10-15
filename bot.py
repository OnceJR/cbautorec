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
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

async def upload_video(chat_id, file_path):
    file_parts = dividir_archivo(file_path) if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024 else [file_path]

    for part in file_parts:
        try:
            await bot.send_file(chat_id, part, supports_streaming=True)
            os.remove(part)
        except Exception as e:
            print(f"Error al enviar el archivo: {e}")

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "¡Hola! Selecciona una opción para comenzar:",
        buttons=[
            [Button.inline("Grabar Clip", b'grabar_clip')],
            [Button.inline("Grabar Completo", b'grabar_completo')],
            [Button.inline("Ver Progreso", b'ver_progreso')]
        ]
    )

@bot.on(events.NewMessage)
async def process_url(event):
    url = event.raw_text
    chat_id = event.chat_id

    if url.startswith("http"):
        user_data[chat_id] = url
        if chat_id in recording_processes:
            await event.respond("Ya hay una grabación en curso. Usa el botón de detener para finalizarla.")
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
        clip_path = await grabar_clip(flujo_url, calidad_clip)
        if clip_path:
            await upload_video(chat_id, clip_path)
            await event.delete()
        else:
            await event.respond("No se pudo grabar el clip.")
    elif calidad == 'completo':
        await event.edit("Grabando transmisión completa...")
        output_file = f'completo_{chat_id}.mp4'
        process = await grabar_completo(flujo_url, output_file)
        recording_processes[chat_id] = process
        await event.delete()
    elif calidad == 'ver_progreso':
        await event.respond("Actualmente no se está realizando ninguna acción.")

# Iniciar el cliente de Telegram
bot.start()
print("El bot está en funcionamiento...")

# Ejecutar el bucle principal
bot.run_until_disconnected()
