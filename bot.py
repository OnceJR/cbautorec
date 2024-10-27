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

LINKS_FILE = 'links.json'
DOWNLOAD_PATH = "/root/cbautorec/"
GDRIVE_PATH = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"
ADMIN_ID = 1170684259  # ID del administrador

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
        await asyncio.sleep(5)
        input_field = driver.find_element(By.NAME, "url")
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        run_button = driver.find_element(By.XPATH, '//button[span[text()="Run"]]')
        run_button.click()
        await asyncio.sleep(15)
        logging.info("Esperando que se procesen los enlaces...")

        m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
        driver.quit()
        
        if m3u8_links:
            return m3u8_links[-1].get_attribute('href')
        else:
            logging.warning("No se encontraron enlaces m3u8.")
            return None
    except Exception as e:
        logging.error(f"Error al extraer el enlace: {e}")
        return None

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
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file}")
            else:
                logging.error(f"Error al subir {file}: {result.stderr}")
        
        await asyncio.sleep(60)

# Descargar con yt-dlp
async def download_with_yt_dlp(m3u8_url, user_id):
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', f"{DOWNLOAD_PATH}%(title)s.%(ext)s"]
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url}")
        await bot.send_message(int(user_id), f"🔴 Iniciando grabación para el enlace: {m3u8_url}")
        process = await asyncio.create_subprocess_exec(*command_yt_dlp)
        await process.wait()
        logging.info("Descarga completa.")
        
    except Exception as e:
        logging.error(f"Error durante la descarga: {e}")
        await bot.send_message(int(user_id), f"❌ Error durante la descarga: {e}")

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
        await event.respond("❗ Enlace no encontrado o comando incorrecto. Usa /eliminar_enlace <enlace>.")

# Manejador para comandos no válidos
@bot.on(events.NewMessage(pattern='^(?!/grabar|/start|/mis_enlaces|/eliminar_enlace).*'))
async def handle_invalid_commands(event):
    await event.respond("⚠️ Comando no reconocido. Usa /grabar, /mis_enlaces o /eliminar_enlace.")

# Procesamiento de URLs enviadas
@bot.on(events.NewMessage)
async def process_url(event):
    if event.text.startswith('/'):
        return
    
    if event.text and is_valid_url(event.text):
        add_link(str(event.sender_id), event.text)
        await event.respond(f"🌐 URL guardada: {event.text}")
        await event.respond(
            "⚠️ <b>¡URL guardada!</b>\n\n"
            "Se ha guardado la URL correctamente. Ahora puedes comenzar la grabación.",
            parse_mode='html'
        )
    else:
        await event.respond("❗ Por favor, envía una URL válida de transmisión.")

# Bienvenida
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "👋 <b>¡Bienvenido al Bot de Grabación!</b>\n\n"
        "Puedes iniciar una grabación enviando una URL válida.\n"
        "Comandos:\n"
        "• <b>/grabar</b> - Inicia monitoreo y grabación automática de transmisión.\n"
        "• <b>/mis_enlaces</b> - Muestra tus enlaces guardados.\n"
        "• <b>/eliminar_enlace</b> - Elimina un enlace guardado."
    )

# Comando del admin para mostrar otros comandos
@bot.on(events.NewMessage(pattern='/admin'))
async def admin_commands(event):
    if event.sender_id == ADMIN_ID:
        await event.respond(
            "⚙️ <b>Comandos de administrador:</b>\n"
            "• <b>/status</b> - Estado del bot.\n"
            "• <b>/reset_links</b> - Reiniciar enlaces."
        )

# Comando para el estado del bot
@bot.on(events.NewMessage(pattern='/status'))
async def status(event):
    if event.sender_id == ADMIN_ID:
        await event.respond("✅ Bot activo y en ejecución.")

# Comando para resetear los enlaces guardados
@bot.on(events.NewMessage(pattern='/reset_links'))
async def reset_links(event):
    if event.sender_id == ADMIN_ID:
        save_links({})
        await event.respond("🔄 Enlaces reiniciados correctamente.")

# Iniciar el bot y tareas
async def main():
    await bot.start()
    await asyncio.gather(verificar_enlaces(), upload_and_delete_mp4_files())

if __name__ == '__main__':
    asyncio.run(main())
