import subprocess
import os
from pyrogram import Client, filters
from flask import Flask

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

# Inicializa Flask
app = Flask(__name__)

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def download_video(url):
    output_file = "video.mp4"  # Nombre del archivo de salida
    command = [
        'yt-dlp',
        '-o', output_file,
        url
    ]
    try:
        subprocess.run(command, check=True)  # Ejecuta el comando de descarga
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al descargar el video: {e}")
        return None

@bot.on_message(filters.command('descargar'))
async def handle_download(client, message):
    await message.reply("Por favor, envía la URL del video de Google Drive.")

@bot.on_message(filters.text & ~filters.command("start"))  # Solo procesar texto que no es el comando /start
async def process_url(client, message):
    url = message.text.strip()
    await message.reply("Descargando video de Google Drive...")

    video_path = await download_video(url)  # Descarga el video

    if video_path and os.path.exists(video_path):
        await bot.send_video(message.chat.id, video_path)  # Envía el video a Telegram
        await message.reply("Video enviado con éxito.")
        
        os.remove(video_path)  # Elimina el archivo del servidor
    else:
        await message.reply("No se pudo descargar el video.")

@bot.on_message(filters.command('start'))
async def send_welcome(client, message):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/descargar - Descarga un video de Google Drive y lo envía al chat."
    )
    await message.reply(welcome_message)

# Ruta de prueba para Flask
@app.route('/')
def home():
    return "El bot de Telegram está en funcionamiento."

# Ejecutar el bot y Flask
if __name__ == '__main__':
    # Ejecutar el bot en un hilo separado
    bot.run()  
    app.run(host='0.0.0.0', port=8000)  # Cambia el puerto si es necesario
