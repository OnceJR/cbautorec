import subprocess
import time
import os
from telethon import TelegramClient, events, Button

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}

async def grabar_clip(url, quality):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}_{quality}.mp4'
    duration = 30  # Duración fija de 30 segundos

    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_file
    ]

    try:
        subprocess.run(command_ffmpeg, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error al grabar el clip: {e}")
        return None

async def upload_video(chat_id, clip_path):
    await bot.send_file(
        chat_id,
        clip_path,
        supports_streaming=True  # Permitir streaming
    )
    os.remove(clip_path)

@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    # Marcar que el usuario está en proceso de grabación
    user_data[event.chat_id] = {'recording': True}
    await event.respond("Por favor, envía la URL de la transmisión de Chaturbate.")

@bot.on(events.NewMessage)
async def process_url(event):
    # Verificar si el usuario está en el proceso de grabar
    if user_data.get(event.chat_id, {}).get('recording'):
        url = event.message.text
        if url.startswith("http"):  # Validar si el mensaje es una URL
            await event.respond("Obteniendo enlace de transmisión...")

            # Crear botones para seleccionar la calidad
            buttons = [
                [Button.inline("Alta", b'alta'), Button.inline("Media", b'media'), Button.inline("Baja", b'baja')]
            ]
            await event.respond("Selecciona la calidad para grabar:", buttons=buttons)

            # Guardar el enlace para usar más tarde
            user_data[event.chat_id]['url'] = url
        else:
            await event.respond("Por favor, envía una URL válida.")
    else:
        # Ignorar otros mensajes si el usuario no ha iniciado el proceso de grabación
        pass

@bot.on(events.CallbackQuery)
async def handle_quality_selection(event):
    quality = event.data.decode('utf-8')

    user_info = user_data.get(event.chat_id)
    if not user_info or 'url' not in user_info:
        await event.respond("No se encontró un enlace válido.")
        return

    flujo_url = user_info['url']
    await event.edit("Grabando clip...")

    clip_path = await grabar_clip(flujo_url, quality)
    if clip_path:
        await upload_video(event.chat_id, clip_path)
        # Limpiar el estado del usuario después de completar la grabación
        user_data.pop(event.chat_id, None)
    else:
        await event.respond("No se pudo grabar el clip.")

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Comandos disponibles:\n"
        "/grabar - Graba un clip de 30 segundos de una transmisión de Chaturbate."
    )
    await event.respond(welcome_message)

# Ejecutar el bot
bot.run_until_disconnected()
