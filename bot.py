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

# Almacena los enlaces y estado de descarga
last_model = None
downloading = False

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

# Función para verificar si la modelo está en línea y manejar la descarga
async def verificar_nuevos_enlaces():
    global last_model, downloading
    while True:
        if last_model and not downloading:
            logging.info(f"Verificando si la modelo está en línea: {last_model}")
            m3u8_link = extract_last_m3u8_link(last_model)
            if m3u8_link:
                logging.info(f"La modelo está en línea. Descargando el enlace .m3u8: {m3u8_link}")
                downloading = True
                output_file = "video_descargado.mp4"
                downloaded_file = download_with_yt_dlp(m3u8_link, output_file)

                if downloaded_file:
                    await bot.send_file(last_model, downloaded_file)  # Envía el archivo al chat
                    os.remove(downloaded_file)  # Elimina el archivo después de enviarlo
                    logging.info(f"Archivo {downloaded_file} enviado y eliminado.")
                else:
                    await bot.send_message(last_model, "No se pudo descargar el video.")
            else:
                logging.info("La modelo no está en línea o no se encontraron enlaces .m3u8.")
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
    if event.text and not event.text.startswith("/") and event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        video_url = reply_msg.text
        last_model = video_url
        await event.respond(f"URL guardada: {last_model}")

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    logging.info(f"Comando /start recibido de {event.sender_id}")
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Aquí están los comandos disponibles:\n"
        "/grabar - Inicia la grabación completa de la transmisión."
    )
    await event.respond(welcome_message)

# Ejecutar el bot y la verificación de nuevos enlaces
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    bot.loop.create_task(verificar_nuevos_enlaces())
    bot.run_until_disconnected()
    driver.quit()
