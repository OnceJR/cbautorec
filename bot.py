import subprocess
import time
import os
from pyrogram import Client, filters

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'  # Nombre del clip
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
        subprocess.run(command_ffmpeg, check=True)  # Ejecuta el comando de grabación
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

@bot.on_message(filters.command('grabar'))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on_message(filters.text & ~filters.command("start"))  # Solo procesar texto que no es el comando /start
async def process_url(client, message):
    url = message.text
    await message.reply("Obteniendo enlace de transmisión...")

    # Enviar botones para seleccionar calidad
    buttons = [
        [("Alta", "alta"), ("Media", "media"), ("Baja", "baja")]
    ]
    await message.reply("Selecciona la calidad para grabar:", reply_markup=buttons)

    # Guardar el enlace para usar más tarde
    client.data[message.chat.id] = url  # Guardar la URL en un diccionario

@bot.on_callback_query()
async def handle_quality_selection(client, callback_query):
    quality = callback_query.data
    await callback_query.answer()  # Responde al callback

    # Obtiene la URL guardada
    flujo_url = client.data.get(callback_query.message.chat.id)
    if not flujo_url:
        await callback_query.message.reply("No se encontró un enlace válido.")
        return

    await callback_query.message.edit_text("Grabando clip...")  # Edita el mensaje

    clip_path = await grabar_clip(flujo_url, quality)  # Graba el clip

    if clip_path:
        await bot.send_video(callback_query.message.chat.id, clip_path)
        await callback_query.message.reply(f"Descarga completada: {flujo_url} ({quality})")
        os.remove(clip_path)  # Elimina el clip después de enviarlo
    else:
        await callback_query.message.reply("No se pudo grabar el clip.")

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
