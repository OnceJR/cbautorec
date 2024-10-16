import asyncio
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
            part_path = f"{file_path}.part{part_num}"
            with open(part_path, 'wb') as part_file:
                part_file.write(f.read(max_size))
            file_parts.append(part_path)
            part_num += 1

    return file_parts

def detener_grabacion(chat_id):
    process = recording_processes.get(chat_id)
    if process:
        try:
            process.terminate()
            del recording_processes[chat_id]
            return True
        except Exception as e:
            print(f"Error al detener la grabación: {e}")
    return False

async def grabar_video(url, output_file, quality="media", duration=None):
    # Configuración de ffmpeg para calidad Alta y Media
    ffmpeg_config = {
        'alta': '-c:v libx264 -crf 20 -preset veryfast -c:a aac -b:a 128k',
        'media': '-c:v libx264 -crf 28 -preset superfast -c:a aac -b:a 96k'
    }

    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-c copy',  # Copiar códecs de la transmisión original si es posible
        ffmpeg_config[quality]
    ]

    if duration:
        command_ffmpeg.extend(['-t', str(duration)])

    command_ffmpeg.append(output_file)

    try:
        process = await asyncio.create_subprocess_exec(
            *command_ffmpeg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        return process
    except Exception as e:
        print(f"Error al iniciar la grabación: {e}")
        return None

async def upload_video(chat_id, file_path):
    file_parts = dividir_archivo(file_path) if os.path.getsize(file_path) > 2 * 1024 * 1024 * 1024 else [file_path]

    for part in file_parts:
        try:
            await bot.send_file(chat_id, part, supports_streaming=True)
            os.remove(part)  # Elimina la parte después de enviarla
        except Exception as e:
            print(f"Error al enviar el archivo: {e}")

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "¡Hola! Aquí están los comandos disponibles:\n"
        "/grabar_clip - Graba un clip de 30 segundos.\n"
        "/grabar_completo - Graba la transmisión completa.\n"
        "/detener - Detiene la grabación en curso."
    )

@bot.on(events.NewMessage(pattern='/grabar_clip'))
async def handle_grabar_clip(event):
    await event.respond("Por favor, envía la URL de la transmisión para grabar un clip.")

@bot.on(events.NewMessage(pattern='/grabar_completo'))
async def handle_grabar_completo(event):
    await event.respond("Por favor, envía la URL de la transmisión para grabar la transmisión completa.")

@bot.on(events.NewMessage(pattern='/detener'))
async def handle_detener(event):
    if detener_grabacion(event.chat_id):
        await event.respond("Grabación detenida.")
        # Asegúrate de que el archivo existe antes de intentar subirlo
        output_file = f'completo_{event.chat_id}.mp4'
        if os.path.exists(output_file):
            await event.respond("Subiendo el archivo...")
            await upload_video(event.chat_id, output_file)
        else:
            await event.respond("No se encontró ningún archivo para subir.")
    else:
        await event.respond("No hay grabación en curso.")

@bot.on(events.NewMessage)
async def process_message(event):
    url = event.raw_text
    chat_id = event.chat_id

    if url.startswith("http://") or url.startswith("https://"):
        user_data[chat_id] = url
        if chat_id in recording_processes:
            await event.respond("Ya hay una grabación en curso. Usa /detener para finalizarla.")
        else:
            await event.respond(
                "Selecciona la calidad o tipo de grabación:",
                buttons=[
                    [Button.inline("Clip Alta", b'clip_alta'), Button.inline("Clip Media", b'clip_media')],
                    [Button.inline("Completo Alta", b'completo_alta'), Button.inline("Completo Media", b'completo_media')]
                ]
            )
    else:
        # Responder solo si no es un comando
        if not url.startswith('/'):
            await event.respond("Por favor, envía un enlace de transmisión válido o usa uno de los comandos disponibles.")

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    global recording_processes
    calidad, tipo = event.data.decode('utf-8').split('_')
    chat_id = event.chat_id
    flujo_url = user_data.get(chat_id)

    if flujo_url:
        await event.edit(f"Grabando {tipo} en calidad {calidad}...")
        if tipo == 'clip':
            output_file = f'clip_{chat_id}.mp4'
            process = await grabar_video(flujo_url, output_file, calidad, duration=30)
        elif tipo == 'completo':
            output_file = f'completo_{chat_id}.mp4'
            process = await grabar_video(flujo_url, output_file, calidad)
        
        if process:
            recording_processes[chat_id] = process
            # Esperar a que el proceso termine
            try:
                await asyncio.wait_for(process.wait(), timeout=3600)  # Timeout de 1 hora
            except asyncio.TimeoutError:
                process.terminate()
                await event.respond("Error: Tiempo de grabación excedido.")
            finally:
                await upload_video(chat_id, output_file)
                del recording_processes[chat_id]
        else:
            await event.respond("No se pudo iniciar la grabación.")
    else:
        await event.respond("Primero debes enviar un enlace de transmisión.")

bot.start()
bot.run_until_disconnected()
