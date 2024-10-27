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
    if user_id not in links:
        links[user_id] = []
    if link not in links[user_id]:
        links[user_id].append(link)
        save_links(links)

def remove_link(user_id, link):
    links = load_links()
    if user_id in links and link in links[user_id]:
        links[user_id].remove(link)
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
        time.sleep(5)  # Aumentar el tiempo de espera
        input_field = driver.find_element(By.NAME, "url")
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        run_button = driver.find_element(By.XPATH, '//button[span[text()="Run"]]')
        run_button.click()
        time.sleep(15)  # Aumentar el tiempo de espera tras hacer clic
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

# Verificación y extracción periódica de enlaces m3u8
async def verificar_enlaces():
    while True:
        links = load_links()
        for user_id, user_links in links.items():
            for link in user_links:
                m3u8_link = extract_last_m3u8_link(link)
                if m3u8_link:
                    logging.info(f"Descargando el enlace m3u8: {m3u8_link}")
                    await download_with_yt_dlp(m3u8_link)
                await asyncio.sleep(2)  # Reanuda la extracción tras cada descarga
        await asyncio.sleep(60)

# Comando de inicio de grabación completa
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    await event.respond(
        "🔴 <b>Inicio de Grabación Completa</b> 🔴\n\n"
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

# Manejador para comandos no válidos
@bot.on(events.NewMessage(pattern='^(?!/grabar|/start|/mis_enlaces|/eliminar_enlace).*'))
async def handle_invalid_commands(event):
    await event.respond("⚠️ Comando no reconocido. Usa /grabar, /mis_enlaces o /eliminar_enlace.")

@bot.on(events.NewMessage)
async def process_url(event):
    # Ignorar comandos para que solo se procesen URLs
    if event.text.startswith('/'):
        return  # Ignorar comandos
    
    # Procesar el mensaje solo si es una URL válida
    if event.text and is_valid_url(event.text):
        add_link(str(event.sender_id), event.text)
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
        "• <b>/grabar</b> - Inicia una grabación completa de transmisión.\n"
        "• <b>/mis_enlaces</b> - Muestra tus enlaces guardados.\n"
        "• <b>/eliminar_enlace</b> - Elimina un enlace guardado.",
        parse_mode='html'
    )

# Ejecutar el bot y la verificación de enlaces
if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    
    bot.loop.create_task(verificar_enlaces())
    bot.run_until_disconnected()
    driver.quit()
