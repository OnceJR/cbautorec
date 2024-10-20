import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
from flask import Flask
import threading  # Para ejecutar Flask en un hilo separado
import asyncio

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Aplicación Flask para mantener el puerto abierto
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

# Hilo separado para Flask
def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Función para obtener el enlace de transmisión con yt-dlp
def obtener_enlace(url):
    command_yt_dlp = [
        'yt-dlp',
        '-f', 'best',
        '-g',
        url
    ]
    try:
        logging.info(f"Ejecutando comando yt-dlp para obtener enlace de: {url}")
        output = subprocess.check_output(command_yt_dlp).decode('utf-8').strip()
        logging.info(f"Enlace obtenido: {output}")
        return output  # Regresa el enlace del flujo
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al obtener el enlace: {e}")
        return None

# Función para grabar el clip con FFmpeg
async def grabar_clip(url):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'  # Nombre del clip
    duration = 30  # Duración fija a 30 segundos

    # Comando para grabar la transmisión usando FFmpeg
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),  # Duración fija a 30 segundos
        '-c:v', 'copy',
        '-c:a', 'copy',
        output_file
    ]

    try:
        logging.info(f"Iniciando grabación del clip de 30 segundos desde {url}")
        subprocess.run(command_ffmpeg)  # Ejecuta el comando de grabación
        logging.info(f"Clip grabado en: {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"Error al grabar el clip: {e}")
        return None

# Función para grabar clips automáticamente cada minuto
async def grabacion_automatica(url, chat_id):
    while True:
        flujo_url = obtener_enlace(url)  # Obtiene el enlace del flujo
        if flujo_url:
            clip_path = await grabar_clip(flujo_url)  # Graba el clip de 30 segundos
            
            if clip_path:
                try:
                    await bot.send_file(chat_id, clip_path)
                    logging.info(f"Clip enviado al chat: {chat_id}")
                    await bot.send_message(chat_id, f"Clip grabado: {flujo_url} (30 segundos)")
                    os.remove(clip_path)  # Elimina el clip después de enviarlo
                    logging.info(f"Clip {clip_path} eliminado del servidor")
                except Exception as e:
                    logging.error(f"Error al enviar el video a Telegram: {e}")
            else:
                logging.error("No se pudo grabar el clip.")
        else:
            logging.error("No se pudo obtener el enlace de la transmisión.")
        await asyncio.sleep(60)  # Espera 60 segundos antes de grabar el siguiente clip

# Manejador de comandos para iniciar la grabación automática
@bot.on(events.NewMessage(pattern='/iniciar'))
async def handle_iniciar(event):
    logging.info(f"Comando /iniciar recibido de {event.sender_id}")
    await event.respond("Por favor, envía la URL de la transmisión para comenzar la grabación automática.")

# Procesar la URL para iniciar la grabación automática
@bot.on(events.NewMessage)
async def process_url(event):
    if event.text and not event.text.startswith("/"):
        url = event.text
        chat_id = event.chat_id
        logging.info(f"URL recibida: {url} de {event.sender_id}")
        await event.respond("Iniciando grabación automática de clips cada minuto...")
        await grabacion_automatica(url, chat_id)

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    logging.info(f"Comando /start recibido de {event.sender_id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/iniciar - Inicia la grabación automática de clips de 30 segundos cada minuto."
    )
    await event.respond(welcome_message)

# Ejecutar el bot y la app Flask en paralelo
if __name__ == '__main__':
    # Inicia el servidor Flask en un hilo separado
    threading.Thread(target=run_flask).start()
    
    # Inicia el bot
    logging.info("Iniciando el bot de Telegram")
    bot.run_until_disconnected()
