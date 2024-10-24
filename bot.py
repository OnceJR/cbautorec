import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.parse import urlparse

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el navegador
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# Almacena el último modelo procesado y estado de descarga
last_model = None
downloading = False

# Validación de URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Función para extraer el último enlace m3u8
def extract_last_m3u8_link(chaturbate_link):
    try:
        driver.get("https://onlinetool.app/ext/m3u8_extractor")
        time.sleep(3)

        input_field = driver.find_element(By.NAME, "url")
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        run_button = driver.find_element(By.XPATH, '//button[span[text()="Run"]]')
        run_button.click()

        time.sleep(5)
        m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
        return m3u8_links[-1].get_attribute('href') if m3u8_links else None
    except Exception as e:
        logging.error(f"Error al extraer el enlace: {e}")
        return None

# Función para descargar usando yt-dlp (asíncrono)
async def download_with_yt_dlp(m3u8_url):
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url]
    try:
        logging.info(f"Iniciando la descarga con yt-dlp desde: {m3u8_url}")
        process = await asyncio.create_subprocess_exec(*command_yt_dlp)
        await process.wait()
        logging.info("Descarga completa.")
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")

# Función para sacar un clip de 30 segundos
def clip_video(source_file, start_time):
    output_file = f"clip_{start_time}.mp4"
    command_ffmpeg = [
        'ffmpeg',
        '-i', source_file,
        '-ss', str(start_time),
        '-t', '30',
        '-c', 'copy',
        output_file
    ]
    try:
        logging.info(f"Sacando clip de 30 segundos desde el segundo {start_time}...")
        subprocess.run(command_ffmpeg)
        logging.info(f"Clip guardado como {output_file}.")
    except Exception as e:
        logging.error(f"Error al crear el clip: {e}")

# Función para verificar enlaces cada minuto
async def verificar_nuevos_enlaces():
    global last_model, downloading
    while True:
        if last_model and not downloading:
            logging.info(f"Verificando enlaces para: {last_model}")
            m3u8_link = extract_last_m3u8_link(last_model)
            if m3u8_link:
                logging.info(f"Descargando el enlace .m3u8: {m3u8_link}")
                downloading = True
                await download_with_yt_dlp(m3u8_link)
                downloading = False
            else:
                logging.info("No se encontraron enlaces .m3u8.")
        await asyncio.sleep(60)  # Espera 1 minuto

# Manejador de comandos para iniciar la grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    global last_model
    logging.info(f"Comando /grabar recibido de {event.sender_id}")
    await event.respond("Por favor, envía la URL de la transmisión para comenzar la grabación completa.")

# Procesar la URL para iniciar la grabación completa
@bot.on(events.NewMessage)
async def process_url(event):
    global last_model
    if event.text and is_valid_url(event.text):
        last_model = event.text
        await event.respond(f"URL guardada: {last_model}")
    else:
        await event.respond("Por favor, envía una URL válida.")

# Manejador para crear clips de 30 segundos
@bot.on(events.NewMessage(pattern='/clip'))
async def handle_clip(event):
    if os.path.exists("video_descargado.mp4"):
        await event.respond("Creando clip de 30 segundos. Por favor espera...")
        clip_video("video_descargado.mp4", 0)  # Cambia el nombre del archivo según corresponda
    else:
        await event.respond("No hay ningún video descargado para crear un clip.")

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    logging.info(f"Comando /start recibido de {event.sender_id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Inicia la grabación completa de la transmisión.\n"
        "/clip - Crea un clip de 30 segundos del video actual."
    )
    await event.respond(welcome_message)

# Ejecutar el bot y la verificación de nuevos enlaces
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    bot.loop.create_task(verificar_nuevos_enlaces())
    bot.run_until_disconnected()
    driver.quit()
