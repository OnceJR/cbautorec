import asyncio
import signal
import os
import psutil
from pyrogram import Client, filters
from flask import Flask
from threading import Thread

# Configuración del cliente de Pyrogram
API_ID = 21660737
API_HASH = "610bd34454377eea7619977040c06c66"
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Configuración del servidor Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "El bot está funcionando correctamente."

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# Función para manejar la señal SIGTERM
async def shutdown(signal, loop):
    print(f"Recibida señal de parada: {signal.name}. Apagando...")
    await app.stop()
    loop.stop()

# Verificar uso de recursos
def check_resource_usage():
    process = psutil.Process(os.getpid())
    mem_usage = process.memory_info().rss / 1024 ** 2  # En MB
    cpu_usage = process.cpu_percent(interval=1)
    print(f"Uso de memoria: {mem_usage:.2f} MB, Uso de CPU: {cpu_usage:.2f}%")

    # Si se supera un umbral de uso de recursos, detener el bot
    if mem_usage > 500:  # Umbral de memoria en MB
        print("El uso de memoria es demasiado alto. Deteniendo el bot...")
        os.kill(os.getpid(), signal.SIGTERM)
    if cpu_usage > 80:  # Umbral de uso de CPU en porcentaje
        print("El uso de CPU es demasiado alto. Deteniendo el bot...")
        os.kill(os.getpid(), signal.SIGTERM)

# Manejar el comando /start
@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("¡Hola! El bot está en funcionamiento.")

# Manejar el comando /grabar
@app.on_message(filters.command("grabar"))
async def grabar_command(client, message):
    await message.reply_text("Por favor, envía la URL de la transmisión de Chaturbate.")

# Función de grabación (ejemplo de función que podrías implementar)
async def grabar_video(url):
    # Lógica de grabación del video
    pass

# Monitorear el uso de recursos en segundo plano
async def monitor_resources():
    while True:
        check_resource_usage()
        await asyncio.sleep(60)  # Verificar cada 60 segundos

# Función principal de ejecución
async def main():
    # Configurar el manejo de señales
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))

    # Iniciar el bot
    await app.start()
    print("Bot iniciado.")

    # Iniciar el monitoreo de recursos
    asyncio.create_task(monitor_resources())

    # Mantener el bot en funcionamiento manualmente
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("Parando el bot...")

if __name__ == "__main__":
    # Iniciar el servidor Flask en un hilo separado
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # Ejecutar el loop principal de asyncio
    asyncio.run(main())
