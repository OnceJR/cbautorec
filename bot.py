import asyncio
import subprocess
import os
import logging
from telethon import TelegramClient, events
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse
import json

# Configuración de la API
API_ID = 24738183
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"
CHANNEL_ID = -2281927010  # ID del canal para el progreso (cambiar por el ID real)

# Inicialización del cliente
bot = TelegramClient('my_bot', API_ID, API_HASH)

# Configurar logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

LINKS_FILE = 'links.json'
DOWNLOAD_PATH = "/root/cbautorec/"
GDRIVE_PATH = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"
ADMIN_ID = 1170684259  # ID del administrador

# Funciones para manejar enlaces
def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_links(links):
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

def add_link(user_id, link):
    links = load_links()
    user_id_str = str(user_id)
    if user_id_str not in links:
        links[user_id_str] = []
    if link not in links[user_id_str]:
        links[user_id_str].append(link)
        save_links(links)

def remove_link(user_id, link):
    links = load_links()
    user_id_str = str(user_id)
    if user_id_str in links and link in links[user_id_str]:
        links[user_id_str].remove(link)
        save_links(links)

# Validación de URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Extracción de enlace m3u8
async def extract_last_m3u8_link(chaturbate_link):
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)

        driver.get("https://onlinetool.app/ext/m3u8_extractor")
        
        wait = WebDriverWait(driver, 10)
        input_field = wait.until(EC.presence_of_element_located((By.NAME, "url")))
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        run_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[span[text()="Run"]]')))
        run_button.click()
        
        logging.info("Esperando que se procesen los enlaces...")
        await asyncio.sleep(15)  # Esperar mientras se procesan

        m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
        driver.quit()
        
        if m3u8_links:
            return m3u8_links[-1].get_attribute('href')
        else:
            logging.warning("No se encontraron enlaces m3u8.")
            return None
    except Exception as e:
        logging.error(f"Error al extraer el enlace: {e}")
        # Reintento de conexión si hubo un error
        for attempt in range(3):  # Intentar 3 veces
            try:
                logging.info(f"Reintentando conexión, intento {attempt + 1}...")
                driver = webdriver.Chrome(options=chrome_options)
                driver.get("https://onlinetool.app/ext/m3u8_extractor")
                # Repetir los pasos para extraer el enlace
                wait = WebDriverWait(driver, 10)
                input_field = wait.until(EC.presence_of_element_located((By.NAME, "url")))
                input_field.clear()
                input_field.send_keys(chaturbate_link)

                run_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[span[text()="Run"]]')))
                run_button.click()

                logging.info("Esperando que se procesen los enlaces...")
                await asyncio.sleep(15)  # Esperar mientras se procesan

                m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
                driver.quit()

                if m3u8_links:
                    return m3u8_links[-1].get_attribute('href')
                else:
                    logging.warning("No se encontraron enlaces m3u8 en el reintento.")
                    return None
            except Exception as retry_exception:
                logging.error(f"Error en el intento {attempt + 1}: {retry_exception}")
                driver.quit()
                await asyncio.sleep(5)  # Esperar antes de reintentar
        return None  # Retornar None si todos los intentos fallan

# Enviar actualización de progreso al canal
async def send_progress_update(message):
    await bot.send_message(CHANNEL_ID, message)

# Subir archivos de forma independiente
async def upload_and_delete_mp4_files():
    while True:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        
        for file in files:
            file_path = os.path.join(DOWNLOAD_PATH, file)
            command = ["rclone", "copy", file_path, GDRIVE_PATH]
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"Subida exitosa: {file}")
                await send_progress_update(f"✅ Subida completada: {file}")
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file}")
            else:
                logging.error(f"Error al subir {file}: {result.stderr}")
                await send_progress_update(f"❌ Error al subir {file}: {result.stderr}")
        
        await asyncio.sleep(60)

# Descargar con yt-dlp
async def download_with_yt_dlp(m3u8_url, user_id):
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', f"{DOWNLOAD_PATH}%(title)s.%(ext)s"]
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url}")
        await bot.send_message(int(user_id), f"🔴 Iniciando grabación para el enlace: {m3u8_url}")
        await send_progress_update(f"🔴 Iniciando grabación para: {m3u8_url}")
        
        process = await asyncio.create_subprocess_exec(*command_yt_dlp)
        await process.wait()
        
        logging.info("Descarga completa.")
        await send_progress_update(f"✅ Descarga completada para: {m3u8_url}")
        
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")
        await bot.send_message(int(user_id), f"❌ Error durante la descarga: {e}")
        await send_progress_update(f"❌ Error durante la descarga: {e}")

# Verificación de enlaces y límite de tareas
async def verificar_enlaces():
    semaphore = asyncio.Semaphore(5)  # Limita a 5 descargas simultáneas
    tasks = []

    while True:
        links = load_links()
        for user_id_str, user_links in links.items():
            user_id = int(user_id_str)
            for link in user_links:
                async with semaphore:
                    m3u8_link = await extract_last_m3u8_link(link)
                    if m3u8_link:
                        task = asyncio.create_task(download_with_yt_dlp(m3u8_link, user_id))
                        tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks)
        await asyncio.sleep(60)

# Comando de inicio de monitoreo y grabación automática
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond(
        "🔴 <b>Inicia monitoreo y grabación automática de una transmisión</b> 🔴\n\n"
        "Por favor, envía la URL de la transmisión para comenzar.",
        parse_mode='html'
    )

# Comando para mostrar enlaces guardados
@bot.on(events.NewMessage(pattern='/mis_enlaces'))
async def show_links(event):
    user_id = str(event.sender_id)
    links = load_links().get(user_id, [])
    if links:
        await event.respond("📌 <b>Enlaces guardados:</b>\n" + "\n".join(links), parse_mode='html')
    else:
        await event.respond("No tienes enlaces guardados.")

# Comando para eliminar un enlace específico
@bot.on(events.NewMessage(pattern='/eliminar_enlace'))
async def delete_link(event):
    user_id = str(event.sender_id)
    link = event.text.split(maxsplit=1)[1] if len(event.text.split()) > 1 else None
    if link and user_id in load_links() and link in load_links()[user_id]:
        remove_link(user_id, link)
        await event.respond(f"✅ Enlace eliminado: {link}")
    else:
        await event.respond("❌ Enlace no encontrado o no válido.")

# Comando para cerrar el bot
@bot.on(events.NewMessage(pattern='/cerrar'))
async def shutdown(event):
    await event.respond("🔴 Cerrando el bot...")
    await bot.disconnect()

# Comando para detener la grabación
@bot.on(events.NewMessage(pattern='/detener'))
async def stop_recording(event):
    # Aquí implementas la lógica para detener la grabación
    await event.respond("🔴 Grabación detenida.")

# Comenzar el bot y las tareas
async def main():
    await bot.start()
    await asyncio.gather(
        verificar_enlaces(),
        upload_and_delete_mp4_files(),
    )

asyncio.run(main())
