import subprocess 
import time
import os
import logging
from telethon import TelegramClient, events
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.parse import urlparse
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
DOWNLOAD_PATH = "/root/cbautorec/"
GDRIVE_PATH = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"

# Cargar y guardar enlaces
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
    user_id_str = str(user_id)  # Convertir a string para guardar
    if user_id_str not in links:
        links[user_id_str] = []
    if link not in links[user_id_str]:
        links[user_id_str].append(link)
        save_links(links)

def remove_link(user_id, link):
    links = load_links()
    user_id_str = str(user_id)  # Convertir a string para acceder
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
def extract_last_m3u8_link(chaturbate_link):
    try:
        driver.get("https://onlinetool.app/ext/m3u8_extractor")
        time.sleep(5)
        input_field = driver.find_element(By.NAME, "url")
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        run_button = driver.find_element(By.XPATH, '//button[span[text()="Run"]]')
        run_button.click()
        time.sleep(15)
        logging.info("Esperando que se procesen los enlaces...")

        # Verificación de los enlaces m3u8
        m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
        logging.info(f"Enlaces encontrados: {len(m3u8_links)}")
        if m3u8_links:
            return m3u8_links[-1].get_attribute('href')
        else:
            logging.warning("No se encontraron enlaces m3u8.")
            return None
    except Exception as e:
        logging.error(f"Error al extraer el enlace: {e}")
        return None

# Subir y eliminar archivos mp4
async def upload_and_delete_mp4_files(user_id):
    try:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        
        for file in files:
            file_path = os.path.join(DOWNLOAD_PATH, file)
            command = ["rclone", "copy", file_path, GDRIVE_PATH]
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"Subida exitosa: {file}")
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # Tamaño en MB
                await bot.send_message(user_id, f"✅ Video subido: {file}\nTamaño: {file_size:.2f} MB\nEnlace: {GDRIVE_PATH}/{file}")
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file}")
            else:
                logging.error(f"Error al subir {file}: {result.stderr}")
                
    except Exception as e:
        logging.error(f"Error en la función de subida y eliminación: {e}")

# Descargar con yt-dlp (asíncrono)
async def download_with_yt_dlp(m3u8_url, user_id):
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', f"{DOWNLOAD_PATH}%(title)s.%(ext)s"]
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url}")
        await bot.send_message(int(user_id), f"🔴 Iniciando grabación para el enlace: {m3u8_url}")  # Convierte user_id a entero
        process = await asyncio.create_subprocess_exec(*command_yt_dlp)
        await process.wait()
        logging.info("Descarga completa.")

        # Llamada a la función de subida y eliminación
        await upload_and_delete_mp4_files(user_id)
        
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")
        await bot.send_message(int(user_id), f"❌ Error durante la descarga: {e}")  # Convierte user_id a entero

# Verificación y extracción periódica de enlaces m3u8
async def verificar_enlaces():
    while True:
        links = load_links()
        tasks = []
        for user_id_str, user_links in links.items():
            user_id = int(user_id_str)  # Convertir a entero
            for link in user_links:
                m3u8_link = extract_last_m3u8_link(link)
                if m3u8_link:
                    tasks.append(download_with_yt_dlp(m3u8_link, user_id))
                else:
                    # Intenta extraer el enlace nuevamente si falló
                    new_m3u8_link = extract_last_m3u8_link(link)
                    if new_m3u8_link:
                        tasks.append(download_with_yt_dlp(new_m3u8_link, user_id))
        if tasks:
            await asyncio.gather(*tasks)
        await asyncio.sleep(60)

# Comando de inicio de monitoreo y grabación automática de una transmisión
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
        await event.respond("❗ Enlace no encontrado o comando incorrecto. Usa /eliminar_enlace <enlace>.")

# Comando para mostrar el estado del bot
@bot.on(events.NewMessage(pattern='/status'))
async def show_status(event):
    await event.respond("✅ El bot está en funcionamiento y listo para grabar.")

# Comando para resetear enlaces
@bot.on(events.NewMessage(pattern='/reset_links'))
async def reset_links(event):
    user_id = str(event.sender_id)
    if user_id == "1170684259":  # Solo el admin puede usar este comando
        os.remove(LINKS_FILE)
        await event.respond("✅ Enlaces reseteados exitosamente.")
    else:
        await event.respond("❗ No tienes permiso para usar este comando.")

# Manejador para comandos no válidos
@bot.on(events.NewMessage(pattern='^(?!/grabar|/start|/mis_enlaces|/eliminar_enlace|/status|/reset_links).*'))
async def handle_invalid_commands(event):
    await event.respond("⚠️ Comando no reconocido. Usa /grabar, /mis_enlaces, /eliminar_enlace, /status o /reset_links.")

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text.startswith('/'):
        return
    
    user_id = event.sender_id
    if is_valid_url(event.text):
        add_link(user_id, event.text)
        await event.respond("✅ Enlace guardado exitosamente.")
    else:
        await event.respond("❌ Enlace no válido. Por favor, envía un enlace de Chaturbate.")

async def main():
    await bot.start()
    asyncio.create_task(verificar_enlaces())
    print("Bot iniciado.")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
