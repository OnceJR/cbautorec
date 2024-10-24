import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.parse import urlparse
from telethon.tl.types import InputFile
import json

# Configuración de la API
API_ID = 24738183
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el navegador
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# Almacenar los enlaces m3u8 en un archivo JSON
LINKS_FILE = 'links.json'

# Cargar enlaces desde el archivo
def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    return []

# Guardar enlaces en el archivo
def save_links(links):
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

# Función para agregar un enlace
def add_link(link):
    links = load_links()
    if link not in links:
        links.append(link)
        save_links(links)

# Función para eliminar un enlace
def remove_link(link):
    links = load_links()
    if link in links:
        links.remove(link)
        save_links(links)

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

# Función para subir archivos a Google Drive y eliminarlos del servidor
async def upload_and_delete_from_server(file_path, file_name):
    rclone_remote = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"

    try:
        # Subir el archivo a Google Drive usando rclone
        logging.info(f"Subiendo {file_name} a Google Drive...")
        result = subprocess.run(['rclone', 'copy', file_path, rclone_remote], check=True)
        if result.returncode == 0:
            logging.info(f"{file_name} subido exitosamente.")
            # Eliminar el archivo local después de la subida
            os.remove(file_path)
            logging.info(f"{file_name} eliminado del servidor.")
        else:
            logging.error(f"Error al subir {file_name}.")
    except Exception as e:
        logging.error(f"Error al subir/eliminar {file_name}: {e}")

# Función para grabar el clip con FFmpeg
async def grabar_clip(m3u8_url):
    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
    duration = 30

    command_ffmpeg = [
        'ffmpeg',
        '-i', m3u8_url,
        '-t', str(duration),
        '-c:v', 'copy',
        '-c:a', 'copy',
        output_file
    ]
    try:
        logging.info(f"Iniciando la grabación del clip: {output_file}")
        await asyncio.create_subprocess_exec(*command_ffmpeg)
        logging.info("Clip grabado exitosamente.")
        
        # Subir y eliminar el archivo
        await upload_and_delete_from_server(output_file, output_file)
    except Exception as e:
        logging.error(f"Error al grabar el clip: {e}")

# Función para listar archivos no eliminados
def list_unremoved_files(folder):
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    return files

# Función para enviar archivos a Telegram y luego borrarlos
async def send_and_delete_files(event, folder):
    files = list_unremoved_files(folder)
    if files:
        for file in files:
            file_path = os.path.join(folder, file)
            await event.respond(f"Enviando archivo: {file}")
            await bot.send_file(event.chat_id, InputFile(file_path))
            os.remove(file_path)
            logging.info(f"Archivo {file} enviado y borrado.")
    else:
        await event.respond("No se encontraron archivos pendientes.")

# Verificación de enlaces en cola
async def verificar_enlaces():
    while True:
        links = load_links()
        for link in links:
            m3u8_link = extract_last_m3u8_link(link)
            if m3u8_link:
                logging.info(f"Descargando el enlace .m3u8: {m3u8_link}")
                await download_with_yt_dlp(m3u8_link)
                remove_link(link)
            else:
                logging.info("No se encontraron enlaces .m3u8.")
        await asyncio.sleep(60)  # Espera 1 minuto

# Manejador de comandos para iniciar la grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond("Por favor, envía la URL de la transmisión para comenzar la grabación completa.")

# Manejador para comando /clip (nueva URL para el clip)
@bot.on(events.NewMessage(pattern='/clip'))
async def handle_clip_command(event):
    await event.respond("Por favor, envía la URL de la transmisión para extraer un clip de 30 segundos.")

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text and is_valid_url(event.text):
        if '/clip' in event.raw_text:
            m3u8_link = extract_last_m3u8_link(event.text)
            if m3u8_link:
                await event.respond("Creando clip de 30 segundos. Por favor espera...")
                await grabar_clip(m3u8_link)
                await send_and_delete_files(event, ".")
            else:
                await event.respond("No se encontraron enlaces .m3u8.")
        else:
            add_link(event.text)
            await event.respond(f"URL guardada: {event.text}")
    else:
        await event.respond("Por favor, envía una URL válida.")

# Manejador para comando /enviar_archivos
@bot.on(events.NewMessage(pattern='/enviar_archivos'))
async def handle_send_files(event):
    await send_and_delete_files(event, ".")

# Manejador para comando /start
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    welcome_message = (
        "¡Hola! Bienvenido a mi bot.\n\n"
        "Comandos disponibles:\n"
        "/grabar - Inicia la grabación completa de la transmisión.\n"
        "/clip - Extrae un clip de 30 segundos desde el inicio de la transmisión.\n"
        "/enviar_archivos - Envía archivos no eliminados."
    )
    await event.respond(welcome_message)

# Ejecutar el bot y la verificación de enlaces
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    
    bot.loop.create_task(verificar_enlaces())
    bot.run_until_disconnected()
    driver.quit()
