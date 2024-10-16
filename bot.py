import os
import subprocess
import time
import logging

from telethon import TelegramClient, events, Button

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Diccionario para almacenar datos de los usuarios y procesos de grabación
user_data = {}
recording_processes = {}

def dividir_archivo(file_path, max_size=2 * 1024 * 1024 * 1024):  # 2 GB
    """Divide un archivo en partes más pequeñas si supera el tamaño máximo."""
    file_parts = []
    file_size = os.path.getsize(file_path)
    part_num = 1

    with open(file_path, 'rb') as f:
        while f.tell() < file_size:
            part_path = f"{file_path}_part{part_num}.mp4"
            with open(part_path, 'wb') as part_file:
                data = f.read(max_size)  # Leer el bloque de datos
                if not data:  # Salir del bucle si no hay más datos
                    break
                part_file.write(data)
            file_parts.append(part_path)
            part_num += 1

    return file_parts

def detener_grabacion(chat_id):
    """Detiene la grabación en curso para el chat_id dado."""
    process = recording_processes.get(chat_id)
    if process and process.poll() is None:
        process.terminate()
        del recording_processes[chat_id]
        return True
    return False

async def grabar_completo(url, output_file):
    """Graba la transmisión completa en un archivo."""
    command_ffmpeg = [
        'ffmpeg', '-i', url, '-c:v', 'libx264', '-preset', 'fast', '-crf',
        '23', '-c:a', 'aac', '-movflags', '+faststart', output_file
    ]

    try:
        process = subprocess.Popen(command_ffmpeg)
        return process
    except Exception as e:
        print(f"Error al iniciar la grabación: {e}")
        return None

async def grabar_clip(url, quality, duration=30):
    """Graba un clip de la transmisión con la duración especificada."""
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'

    command_ffmpeg = [
        'ffmpeg', '-i', url, '-t', str(duration), '-c:v', 'libx264',
        '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-movflags',
        '+faststart', output_file
    ]

    try:
        subprocess.run(command_ffmpeg, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

async def upload_video(chat_id, file_path):
    """Sube el video al chat especificado, dividiéndolo si es necesario."""
    file_parts = dividir_archivo(
        file_path) if os.path.getsize(
            file_path) > 2 * 1024 * 1024 * 1024 else [file_path]

    try:
        for part in file_parts:
            logging.info(f"Subiendo archivo a Telegram: {part}")  # Log de subida
            with open(part, "rb") as video_file:
                await bot.send_video(chat_id=chat_id,
                                     video=video_file,
                                     supports_streaming=True)
    except Exception as e:
        print(f"Error al enviar el archivo: {e}")
        raise  # Re-lanzar la excepción para que sea manejada en handle_quality_selection
    finally:
        for part in file_parts:
            if os.path.exists(part):
                os.remove(part)

    # Eliminar el archivo original después de dividirlo y enviar las partes
    if len(file_parts) > 1 and os.path.exists(file_path):
        os.remove(file_path)

@bot.on(events.NewMessage(pattern='/detener'))
async def handle_detener(event):
    if detener_grabacion(event.chat_id):
        await event.respond("Grabación detenida. Subiendo el archivo...")
        try:
            await upload_video(event.chat_id, f'completo_{event.chat_id}.mp4')
        except Exception as e:
            await event.respond(f"Error al subir el archivo: {e}")
    else:
        await event.respond("No hay grabación en curso.")

@bot.on(events.NewMessage)
async def process_message(event):
    """Procesa los mensajes del usuario."""
    url = event.raw_text
    chat_id = event.chat_id

    if url.startswith("http://") or url.startswith("https://"):
        user_data[chat_id] = url
        if chat_id in recording_processes:
            await event.respond(
                "Ya hay una grabación en curso. Usa /detener para finalizarla.")
        else:
            await event.respond("Selecciona el tipo de grabación:",
                                 buttons=[
                                     [Button.inline("Clip", b'clip'),
                                      Button.inline("Completo", b'completo')]
                                 ])
    else:
        # Responder solo si no es un comando
        if not url.startswith('/'):
            await event.respond("Por favor, envía un enlace de transmisión válido.")

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    """Maneja la selección de calidad o tipo de grabación."""
    tipo_grabacion = event.data.decode('utf-8')
    chat_id = event.chat_id
    flujo_url = user_data.get(chat_id)
    clip_path = None  # Inicializar clip_path

    try:
        if tipo_grabacion == 'clip':
            await event.edit("Grabando clip de 30 segundos...")

            clip_path = await grabar_clip(flujo_url, "estandar")  # Calidad estándar por defecto
            if clip_path:
                await upload_video(chat_id, clip_path)
                await event.respond(f"Descarga completada (30 segundos)")
            else:
                await event.respond("No se pudo grabar el clip.")

        elif tipo_grabacion == 'completo':
            await event.edit("Grabando transmisión completa...")
            output_file = f'completo_{chat_id}.mp4'
            process = await grabar_completo(flujo_url, output_file)
            if process:
                recording_processes[chat_id] = process
            else:
                await event.respond("No se pudo iniciar la grabación.")

    except Exception as e:
        print(f"Error al procesar la grabación: {e}")
    finally:  # Mover la eliminación del archivo aquí
        if tipo_grabacion == 'clip' and clip_path and os.path.exists(
                clip_path):
            os.remove(clip_path)

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    """Envía un mensaje de bienvenida con los comandos disponibles."""
    await event.respond(
        "¡Hola! Simplemente envía un enlace de transmisión para comenzar a grabar.\n"
        "Puedes usar /detener para detener la grabación en curso.")

bot.start()
bot.run_until_disconnected()
