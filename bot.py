import subprocess
import time
import os
import logging
from pyrogram import Client, filters
from flask import Flask
import threading  # Para ejecutar Flask en un hilo separado

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

# Manejadores de comandos y mensajes en Pyrogram
@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    logging.info(f"Comando /grabar recibido de {message.from_user.id}")
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on_message(filters.text & ~filters.command("start"))  # Solo procesar texto que no es el comando /start
async def process_url(client, message):
    url = message.text
    logging.info(f"URL recibida: {url} de {message.from_user.id}")
    await message.reply("Obteniendo enlace de transmisión...")

    flujo_url = obtener_enlace(url)  # Obtiene el enlace del flujo

    if flujo_url:
        await message.reply("Grabando clip de 30 segundos...")
        clip_path = await grabar_clip(flujo_url)  # Graba el clip
        
        if clip_path:
            try:
                await bot.send_video(message.chat.id, clip_path)
                logging.info(f"Clip enviado al chat: {message.chat.id}")
                await message.reply(f"Descarga completada: {flujo_url} (30 segundos)")
                os.remove(clip_path)  # Elimina el clip después de enviarlo
                logging.info(f"Clip {clip_path} eliminado del servidor")
            except Exception as e:
                logging.error(f"Error al enviar el video a Telegram: {e}")
        else:
            logging.error("No se pudo grabar el clip.")
            await message.reply("No se pudo grabar el clip.")
    else:
        logging.error("No se pudo obtener el enlace de la transmisión.")
        await message.reply("No se pudo obtener el enlace de la transmisión.")

@bot.on_message(filters.command('start'))
async def send_welcome(client, message):
    logging.info(f"Comando /start recibido de {message.from_user.id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await message.reply(welcome_message)

# Ejecutar el bot y la app Flask con puerto "falso"
if __name__ == '__main__':
    # Inicia el servidor Flask en un hilo separado
    threading.Thread(target=run_flask).start()
    
    # Inicia el bot
    logging.info("Iniciando el bot de Telegram")
    bot.run()
