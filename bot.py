import asyncio
import os
import psutil
import signal
import subprocess
from pyrogram import Client, filters

# Configuración del cliente de Pyrogram
API_ID = 21660737
API_HASH = "610bd34454377eea7619977040c06c66"
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Verificar uso de recursos
def check_resource_usage():
    process = psutil.Process(os.getpid())
    mem_usage = process.memory_info().rss / 1024 ** 2  # En MB
    cpu_usage = process.cpu_percent(interval=1)
    print(f"Uso de memoria: {mem_usage:.2f} MB, Uso de CPU: {cpu_usage:.2f}%")

    if mem_usage > 500:  # Umbral de memoria en MB
        print("El uso de memoria es demasiado alto. Deteniendo el bot...")
        os.kill(os.getpid(), signal.SIGTERM)
    if cpu_usage > 80:  # Umbral de uso de CPU en porcentaje
        print("El uso de CPU es demasiado alto. Deteniendo el bot...")
        os.kill(os.getpid(), signal.SIGTERM)

# Función para grabar clip
async def grabar_clip(url, chat_id):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'  # Nombre del clip
    duration = 30  # Duración del clip en segundos

    # Comando para grabar la transmisión usando FFmpeg
    command_ffmpeg = [
        'ffmpeg',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'copy',
        '-c:a', 'copy',
        output_file
    ]

    try:
        subprocess.run(command_ffmpeg, timeout=duration + 5)  # Timeout con un margen
        with open(output_file, 'rb') as video_file:
            await app.send_video(chat_id, video_file)
        os.remove(output_file)  # Eliminar el clip después de enviarlo
    except Exception as e:
        await app.send_message(chat_id, f"Ocurrió un error al grabar el clip: {e}")

# Manejar el comando /grabar
@app.on_message(filters.command("grabar"))
async def grabar_command(client, message):
    await message.reply_text("Por favor, envía la URL de la transmisión de Chaturbate.")
    await app.listen(message.chat.id, timeout=60)  # Escuchar por la URL

# Evento para mantener el bot en ejecución
stop_event = asyncio.Event()

# Función principal de ejecución
async def main():
    await app.start()
    print("Bot iniciado.")
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    finally:
        await app.stop()
        print("Bot detenido.")

# Señal para detener el bot de manera segura
def shutdown(*args):
    stop_event.set()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    asyncio.run(main())
