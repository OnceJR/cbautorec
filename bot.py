import asyncio
import logging
import re
import subprocess
import os
import glob
from telethon import TelegramClient, events
from telethon.tl.types import InputMediaUploadedDocument
import yt_dlp

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Credenciales de la API de Telethon
API_ID = 24738183
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"

# Inicializar el cliente de Telegram
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Diccionario para almacenar las grabaciones activas
grabaciones_activas = {}

async def obtener_url_stream(url, calidad):
    """Obtiene la URL de la transmisión en vivo con yt-dlp."""
    ydl_opts = {
        'format': f'bestvideo[height<={calidad}]+bestaudio/best[height<={calidad}]',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url']

async def grabar_clip(chat_id, url, calidad):
    """Graba un clip de 30 segundos de la transmisión en vivo."""
    try:
        # Obtener la URL de la transmisión
        stream_url = await obtener_url_stream(url, calidad)

        # Comando ffmpeg para grabar un clip de 30 segundos
        comando = f'ffmpeg -i "{stream_url}" -c copy -t 30 clip.mp4'

        # Ejecutar el comando ffmpeg
        proceso = await asyncio.create_subprocess_shell(comando)
        await proceso.wait()

        # Enviar el clip a Telegram
        await enviar_video(chat_id, "clip.mp4")
    except Exception as e:
        logger.error(f"Error al grabar clip: {e}")
        await bot.send_message(chat_id, f"Error al grabar el clip: {e}")

async def grabar_completo(chat_id, url, calidad):
    """Graba la transmisión en vivo completa."""
    try:
        # Obtener la URL de la transmisión
        stream_url = await obtener_url_stream(url, calidad)

        # Comando ffmpeg para grabar la transmisión completa
        comando = f'ffmpeg -i "{stream_url}" -c copy grabacion_completa.mp4'

        # Ejecutar el comando ffmpeg
        proceso = await asyncio.create_subprocess_shell(comando)
        grabaciones_activas[chat_id] = proceso
        await proceso.wait()

        # Enviar la grabación completa a Telegram
        await enviar_video(chat_id, "grabacion_completa.mp4")
        del grabaciones_activas[chat_id]
    except Exception as e:
        logger.error(f"Error al grabar la transmisión completa: {e}")
        await bot.send_message(chat_id, f"Error al grabar la transmisión completa: {e}")

async def detener_grabacion(chat_id):
    """Detiene la grabación en curso."""
    try:
        if chat_id in grabaciones_activas:
            proceso = grabaciones_activas[chat_id]
            proceso.terminate()
            del grabaciones_activas[chat_id]
            await bot.send_message(chat_id, "Grabación detenida.")
        else:
            await bot.send_message(chat_id, "No hay ninguna grabación en curso.")
    except Exception as e:
        logger.error(f"Error al detener la grabación: {e}")
        await bot.send_message(chat_id, f"Error al detener la grabación: {e}")

async def enviar_video(chat_id, nombre_archivo):
    """Envía el video a Telegram, dividiéndolo si es necesario."""
    try:
        # Obtener el tamaño del archivo
        tamano_archivo = os.path.getsize(nombre_archivo)

        # Si el archivo es mayor a 2 GB, dividirlo en partes
        if tamano_archivo > 2 * 1024 * 1024 * 1024:
            await bot.send_message(chat_id, "El archivo es demasiado grande. Dividiendo en partes...")
            await dividir_y_enviar_video(chat_id, nombre_archivo)
        else:
            # Enviar el video a Telegram
            async with bot.action(chat_id, 'document'):
                await bot.send_file(
                    chat_id,
                    nombre_archivo,
                    supports_streaming=True,
                    caption=f"Aquí está tu video: {nombre_archivo}"
                )
    except Exception as e:
        logger.error(f"Error al enviar el video: {e}")
        await bot.send_message(chat_id, f"Error al enviar el video: {e}")

async def dividir_y_enviar_video(chat_id, nombre_archivo):
    """Divide el video en partes y las envía a Telegram."""
    try:
        # Comando ffmpeg para dividir el video
        comando = f'ffmpeg -i "{nombre_archivo}" -c copy -fs 2G -f segment "parte_%03d.mp4"'

        # Ejecutar el comando ffmpeg
        proceso = await asyncio.create_subprocess_shell(comando)
        await proceso.wait()

        # Enviar las partes a Telegram
        async with bot.action(chat_id, 'document'):
            for archivo in glob.glob("parte_*.mp4"):
                await bot.send_file(
                    chat_id,
                    archivo,
                    supports_streaming=True,
                    caption=f"Parte del video: {archivo}"
                )
    except Exception as e:
        logger.error(f"Error al dividir y enviar el video: {e}")
        await bot.send_message(chat_id, f"Error al dividir y enviar el video: {e}")

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Envía un mensaje de bienvenida cuando se inicia el bot."""
    await event.respond("Hola! Soy un bot que puede grabar transmisiones en vivo. Usa /grabar_clip, /grabar_completo o /detener para interactuar conmigo.")

@bot.on(events.NewMessage(pattern='/grabar_clip'))
async def grabar_clip_handler(event):
    """Maneja el comando /grabar_clip."""
    try:
        # Obtener la URL de la transmisión del mensaje
        url = re.search(r'(https?://[^\s]+)', event.message.text).group(1)

        # Preguntar por la calidad de la grabación
        await event.respond("¿Qué calidad deseas? (Ejemplo: 720, 1080)")

        @bot.on(events.NewMessage(from_users=event.sender_id))
        async def obtener_calidad(event):
            try:
                calidad = int(event.message.text)
                await event.respond("Grabando clip...")
                await grabar_clip(event.chat_id, url, calidad)
            except ValueError:
                await event.respond("Calidad inválida. Por favor, ingresa un número.")
            finally:
                bot.remove_event_handler(obtener_calidad)

    except AttributeError:
        await event.respond("Por favor, proporciona una URL válida.")

@bot.on(events.NewMessage(pattern='/grabar_completo'))
async def grabar_completo_handler(event):
    """Maneja el comando /grabar_completo."""
    try:
        # Obtener la URL de la transmisión del mensaje
        url = re.search(r'(https?://[^\s]+)', event.message.text).group(1)

        # Preguntar por la calidad de la grabación
        await event.respond("¿Qué calidad deseas? (Ejemplo: 720, 1080)")

        @bot.on(events.NewMessage(from_users=event.sender_id))
        async def obtener_calidad(event):try:
                calidad = int(event.message.text)
                await event.respond("Grabando transmisión completa...")
                await grabar_completo(event.chat_id, url, calidad)
            except ValueError:
                await event.respond("Calidad inválida. Por favor, ingresa un número.")
            finally:
                bot.remove_event_handler(obtener_calidad)

    except AttributeError:
        await event.respond("Por favor, proporciona una URL válida.")

@bot.on(events.NewMessage(pattern='/detener'))
async def detener_grabacion_handler(event):
    """Maneja el comando /detener."""
    await detener_grabacion(event.chat_id)

# Iniciar el bot
if __name__ == '__main__':
    logger.info("Bot iniciado.")
    bot.run_until_disconnected()
