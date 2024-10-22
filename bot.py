import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
import threading
import asyncio

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Función para obtener el enlace de transmisión con yt-dlp
def obtener_enlace(url):
    command_yt_dlp = [
        'yt-dlp',
        '--cookies', 'chaturbate_cookies.txt',  # Ruta a tu archivo de cookies
        '--add-header', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
        '-f', 'best',
        '-g',
        url
    ]
    try:
        logging.info(f"Ejecutando comando yt-dlp para obtener enlace de: {url}")
        output = subprocess.check_output(command_yt_dlp).decode('utf-8').strip()
        logging.info(f"Enlace obtenido: {output}")
        return output
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al obtener el enlace: {e}")
        return None

# Función para grabar la transmisión completa
async def grabar_transmision(url, chat_id):
    output_file = f'grabacion_completa_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
    temp_file = f'temp_{time.strftime("%Y%m%d_%H%M%S")}.mp4'  # Archivo temporal durante la grabación

    # Usar archivo temporal para grabar
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-c:v', 'copy',
        '-c:a', 'copy',
        temp_file  # Guardar en archivo temporal
    ]
    
    logging.info(f"Iniciando grabación completa desde {url}")
    proceso = subprocess.Popen(command_ffmpeg)
    
    # Espera para detener la grabación
    await bot.send_message(chat_id, "Grabación iniciada. Envíe /detener para detener la grabación.")
    return proceso, temp_file, output_file

# Función para detener la grabación y remuxear el archivo
async def detener_grabacion(proceso, chat_id, temp_file, output_file):
    proceso.terminate()  # Detiene la grabación
    await bot.send_message(chat_id, "Grabación detenida. Procesando archivo...")

    # Remuxear para asegurar que el archivo MP4 sea válido
    command_remux = [
        'ffmpeg',
        '-i', temp_file,
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-movflags', '+faststart',  # Optimiza para reproducción en streaming
        output_file
    ]
    
    try:
        subprocess.run(command_remux)  # Remuxea el archivo
        logging.info(f"Archivo {output_file} generado correctamente.")
        
        # Enviar archivo a Telegram
        await bot.send_file(chat_id, output_file)
        logging.info(f"Archivo {output_file} enviado al chat: {chat_id}")
        
        os.remove(temp_file)  # Elimina el archivo temporal
        os.remove(output_file)  # Elimina el archivo después de enviarlo
        logging.info(f"Archivos {temp_file} y {output_file} eliminados del servidor")
    except Exception as e:
        logging.error(f"Error al procesar el archivo grabado: {e}")

# Manejador de comandos para iniciar la grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    logging.info(f"Comando /grabar recibido de {event.sender_id}")
    await event.respond("Por favor, envía la URL de la transmisión para comenzar la grabación completa.")

# Procesar la URL para iniciar la grabación completa
@bot.on(events.NewMessage)
async def process_url(event):
    if event.text and not event.text.startswith("/"):
        url = event.text
        chat_id = event.chat_id
        flujo_url = obtener_enlace(url)
        
        if flujo_url:
            proceso, temp_file, output_file = await grabar_transmision(flujo_url, chat_id)
            
            # Manejador para detener la grabación
            @bot.on(events.NewMessage(pattern='/detener'))
            async def handle_detener(event):
                logging.info(f"Comando /detener recibido de {event.sender_id}")
                await detener_grabacion(proceso, chat_id, temp_file, output_file)
        else:
            await event.respond("No se pudo obtener el enlace de la transmisión.")

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    logging.info(f"Comando /start recibido de {event.sender_id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Inicia la grabación completa de la transmisión.\n"
        "/detener - Detiene la grabación y sube el archivo a Telegram."
    )
    await event.respond(welcome_message)

# Ejecutar el bot
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    bot.run_until_disconnected()
