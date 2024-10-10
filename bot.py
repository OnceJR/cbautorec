import subprocess
import time
import os
from pyrogram import Client, filters

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def obtener_enlace(url):
    command_yt_dlp = [
        'yt-dlp',
        '-f', 'best',
        '-g',
        url
    ]
    try:
        output = subprocess.check_output(command_yt_dlp).decode('utf-8').strip()
        return output  # Regresa el enlace del flujo
    except subprocess.CalledProcessError as e:
        print(f"Error al obtener el enlace: {e}")
        return None

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

    subprocess.run(command_ffmpeg)  # Ejecuta el comando de grabación
    return output_file

@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on_message(filters.text & ~filters.command("start"))  # Solo procesar texto que no es el comando /start
async def process_url(client, message):
    url = message.text
    await message.reply("Obteniendo enlace de transmisión...")

    flujo_url = obtener_enlace(url)  # Obtiene el enlace del flujo

    if flujo_url:
        await message.reply("Grabando clip de 30 segundos...")
        clip_path = await grabar_clip(flujo_url)  # Graba el clip
        
        if clip_path:
            await bot.send_video(message.chat.id, clip_path)
            await message.reply(f"Descarga completada: {flujo_url} (30 segundos)")
            os.remove(clip_path)  # Elimina el clip después de enviarlo
        else:
            await message.reply("No se pudo grabar el clip.")
    else:
        await message.reply("No se pudo obtener el enlace de la transmisión.")

@bot.on_message(filters.command('start'))
async def send_welcome(client, message):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await message.reply(welcome_message)

# Ejecutar el bot
if __name__ == '__main__':
    bot.run()