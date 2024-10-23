import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el navegador
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# Función para extraer el último enlace m3u8
def extract_last_m3u8_link(chaturbate_link):
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

# Función para descargar usando yt-dlp
def download_with_yt_dlp(m3u8_url, output_file):
    command_yt_dlp = [
        'yt-dlp',
        '-f', 'best',
        '-o', output_file,
        m3u8_url
    ]

    try:
        logging.info(f"Iniciando la descarga con yt-dlp desde: {m3u8_url}")
        subprocess.run(command_yt_dlp)
        logging.info("Descarga completa.")
        return output_file
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")
        return None

# Función para descargar y crear un clip de 30 segundos
async def download_and_clip(m3u8_url, chat_id):
    output_file = "video_descargado.mp4"
    downloaded_file = download_with_yt_dlp(m3u8_url, output_file)

    if downloaded_file:
        await bot.send_file(chat_id, downloaded_file)  # Envía el archivo al chat
        os.remove(downloaded_file)  # Elimina el archivo después de enviarlo
        logging.info(f"Archivo {downloaded_file} enviado y eliminado.")
    else:
        await bot.send_message(chat_id, "No se pudo descargar el video.")

# Manejador de comandos para iniciar la grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    logging.info(f"Comando /grabar recibido de {event.sender_id}")
    await event.respond("Por favor, envía la URL de la transmisión para comenzar la grabación completa.")

# Procesar la URL para iniciar la grabación completa
@bot.on(events.NewMessage)
async def process_url(event):
    if event.text and not event.text.startswith("/") and event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        video_url = reply_msg.text
        await event.respond("Iniciando descarga del video...")
        await download_and_clip(video_url, event.chat_id)

# Manejador para crear clips de 30 segundos
@bot.on(events.NewMessage(pattern='/clip'))
async def handle_clip(event):
    logging.info(f"Comando /clip recibido de {event.sender_id}")
    await event.respond("Por favor, envía la URL del video para crear un clip de 30 segundos.")

# Procesar la URL para crear un clip de 30 segundos
@bot.on(events.NewMessage)
async def process_clip_url(event):
    if event.text and not event.text.startswith("/") and event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        video_url = reply_msg.text
        await event.respond("Creando clip de 30 segundos. Por favor espera...")
        
        output_file = "clip.mp4"
        command_ffmpeg = [
            'ffmpeg',
            '-i', video_url,
            '-ss', '0',
            '-t', '30',
            '-c', 'copy',
            output_file
        ]

        try:
            subprocess.run(command_ffmpeg)
            await bot.send_file(event.chat_id, output_file)  # Envía el clip al chat
            os.remove(output_file)  # Elimina el archivo después de enviarlo
            logging.info(f"Clip {output_file} enviado y eliminado.")
        except Exception as e:
            logging.error(f"Error al crear el clip: {e}")
            await event.respond("Error al crear el clip.")

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    logging.info(f"Comando /start recibido de {event.sender_id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Inicia la grabación completa de la transmisión.\n"
        "/clip - Crea un clip de 30 segundos de la URL respondida."
    )
    await event.respond(welcome_message)

# Ejecutar el bot
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    bot.run_until_disconnected()
    driver.quit()
