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

LINKS_FILE = 'links.json'
is_recording = False

# Cargar y guardar enlaces
def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_links(links):
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

def add_link(link):
    links = load_links()
    if link not in links:
        links.append(link)
        save_links(links)

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

# Extracción de enlace m3u8
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

# Descargar con yt-dlp (asíncrono)
async def download_with_yt_dlp(m3u8_url):
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url]
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url}")
        process = await asyncio.create_subprocess_exec(*command_yt_dlp)
        await process.wait()
        logging.info("Descarga completa.")
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")

# Subir a Google Drive y eliminar del servidor
async def upload_and_delete_from_server(file_path, file_name):
    rclone_remote = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"
    try:
        logging.info(f"Subiendo {file_name} a Google Drive...")
        result = subprocess.run(['rclone', 'copy', file_path, rclone_remote], check=True)
        if result.returncode == 0:
            logging.info(f"{file_name} subido exitosamente.")
            os.remove(file_path)
            logging.info(f"{file_name} eliminado del servidor.")
        else:
            logging.error(f"Error al subir {file_name}.")
    except Exception as e:
        logging.error(f"Error al subir/eliminar {file_name}: {e}")

# Grabación de clip
async def grabar_clip(m3u8_url):
    global is_recording
    if is_recording:
        logging.info("Ya hay una grabación activa.")
        return

    output_file = f'clip_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
    duration = 30

    command_ffmpeg = [
        'ffmpeg', '-i', m3u8_url, '-t', str(duration), '-c:v', 'copy', '-c:a', 'copy', output_file
    ]

    try:
        logging.info(f"Iniciando grabación: {output_file}")
        is_recording = True
        await asyncio.create_subprocess_exec(*command_ffmpeg)
        logging.info("Clip grabado exitosamente.")
        
        await upload_and_delete_from_server(output_file, output_file)
    except Exception as e:
        logging.error(f"Error al grabar: {e}")
    finally:
        is_recording = False

# Verificación y extracción periódica de enlaces m3u8
async def verificar_enlaces():
    while True:
        links = load_links()
        for link in links:
            m3u8_link = extract_last_m3u8_link(link)
            if m3u8_link:
                logging.info(f"Descargando el enlace m3u8: {m3u8_link}")
                await download_with_yt_dlp(m3u8_link)
                remove_link(link)
            await asyncio.sleep(2) # Reanuda la extracción tras cada descarga
        await asyncio.sleep(60) 

# Comando de inicio de grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond(
        "🔴 <b>Inicio de Grabación Completa</b> 🔴\n\n"
        "Por favor, envía la URL de la transmisión para comenzar.",
        parse_mode='html'  # Especifica el modo de parseo
    )

# Manejador para comandos válidos
@bot.on(events.NewMessage(pattern='^(?!/grabar|/start|/clip|/enviar_archivos).*'))
async def handle_invalid_commands(event):
    await event.respond("⚠️ Comando no reconocido. Usa /grabar para iniciar la grabación completa.")

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text and is_valid_url(event.text):
        add_link(event.text)
        await event.respond(f"🌐 URL guardada: {event.text}")
    else:
        await event.respond("❗ Por favor, envía una URL válida de transmisión.")

# Bienvenida
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "👋 <b>¡Bienvenido al Bot de Grabación!</b>\n\n"
        "Puedes iniciar una grabación enviando una URL válida.\n"
        "Comandos:\n"
        "• <b>/grabar</b> - Inicia una grabación completa de transmisión.",
        parse_mode='html'  # Especifica el modo de parseo
    )

# Ejecutar el bot y la verificación de enlaces
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    
    bot.loop.create_task(verificar_enlaces())
    bot.run_until_disconnected()
    driver.quit()
