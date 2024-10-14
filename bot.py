from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
import time
import os

API_ID = 21660737
API_HASH = "610bd34454377eea7619977040c06c66"
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

url_mapping = {}  # Mapa para almacenar URLs

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

def grabar_clip(url):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'  # Nombre del clip
    duration = 30  # Duración del clip en segundos

    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'copy',
        '-c:a', 'copy',
        output_file,
        '-vf', 'thumbnail'  # Filtra para crear un thumbnail
    ]
    try:
        subprocess.run(command_ffmpeg, timeout=duration + 5)  # Timeout con un margen
        return output_file
    except subprocess.TimeoutExpired:
        pass  # Ignorar si se alcanza el tiempo de espera

@app.on_message(filters.command("grabar"))
async def handle_grabar(client, message):
    await message.reply("Por favor, envía la URL de la transmisión de Chaturbate.")
    await app.listen(message.chat.id, timeout=60)  # Escuchar por la URL

@app.on_message(filters.text & filters.private)
async def process_url(client, message):
    url = message.text
    flujo_url = obtener_enlace(url)  # Obtiene el enlace del flujo

    if flujo_url:
        short_id = str(hash(flujo_url))  # Crear un identificador corto
        url_mapping[short_id] = flujo_url  # Guardar la URL en el mapa
        buttons = build_quality_buttons(short_id)
        await message.reply("Selecciona la calidad para grabar:", reply_markup=buttons)
    else:
        await message.reply("No se pudo obtener el enlace de la transmisión.")

def build_quality_buttons(short_id):
    buttons = [
        [InlineKeyboardButton("Baja", callback_data=f"low_{short_id}")],
        [InlineKeyboardButton("Media", callback_data=f"medium_{short_id}")],
        [InlineKeyboardButton("Alta", callback_data=f"high_{short_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

@app.on_callback_query(filters.regex(r'^(low|medium|high)_(\d+)$'))
async def handle_quality_selection(client, callback_query):
    quality = callback_query.data.split('_')[0]
    short_id = callback_query.data.split('_')[1]
    flujo_url = url_mapping[short_id]  # Recupera la URL del diccionario

    await callback_query.answer("Grabando clip...")
    clip_path = grabar_clip(flujo_url)  # Graba el clip

    if clip_path:
        await client.send_video(callback_query.message.chat.id, clip_path)
        os.remove(clip_path)  # Eliminar el clip después de enviarlo
    else:
        await callback_query.message.reply("Ocurrió un error al grabar el clip.")

@app.on_message(filters.command("start"))
async def send_welcome(client, message):
    await message.reply("¡Hola! Usa el comando /grabar para grabar un clip de 30 segundos de una transmisión de Chaturbate.")

app.run()
