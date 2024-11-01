import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
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
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")  # Evita el sandbox cuando se ejecuta como root
chrome_options.add_argument("--headless")  # Ejecuta sin interfaz gráfica
chrome_options.add_argument("--disable-dev-shm-usage")  # Usa /tmp en lugar de /dev/shm para memoria compartida
chrome_options.add_argument("--remote-debugging-port=9222")  # Habilita un puerto para depuración remota

driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)

LINKS_FILE = 'links.json'
DOWNLOAD_PATH = "/root/cbautorec/"
GDRIVE_PATH = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"

AUTHORIZED_USERS = {1170684259, 1218594540}
is_recording = {}  # Diccionario para almacenar el estado de grabación por usuario

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
            
            # Cambiamos subprocess.run por asyncio.create_subprocess_exec
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logging.info(f"Subida exitosa: {file}")

                # Crear enlace compartido
                share_command = ["rclone", "link", GDRIVE_PATH + file]
                share_process = await asyncio.create_subprocess_exec(*share_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                share_stdout, share_stderr = await share_process.communicate()
                
                if share_process.returncode == 0:
                    shared_link = share_stdout.strip().decode('utf-8')
                    await bot.send_message(int(user_id), f"✅ Video subido: {file}\n🔗 Enlace: {shared_link}")
                else:
                    logging.error(f"Error al crear enlace compartido para {file}: {share_stderr.decode('utf-8')}")
                    await bot.send_message(int(user_id), f"❌ Error al crear enlace compartido para: {file}")
                
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file}")
            else:
                logging.error(f"Error al subir {file}: {stderr.decode('utf-8')}")
                await bot.send_message(int(user_id), f"❌ Error al subir el archivo: {file}")  # Notificar al usuario

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
        links = load_links()  # Carga los enlaces guardados
        tasks = []  # Lista para almacenar las tareas de descarga en paralelo
        processed_links = {}  # Diccionario para almacenar enlaces ya procesados

        for user_id_str, user_links in links.items():
            user_id = int(user_id_str)
            for link in user_links:
                # Evita duplicados y asigna el mismo archivo si ya está en proceso
                if link not in processed_links:
                    m3u8_link = extract_last_m3u8_link(link)
                    if m3u8_link:
                        # Lanza la tarea de descarga en segundo plano
                        task = asyncio.create_task(download_with_yt_dlp(m3u8_link, user_id))
                        tasks.append(task)  # Agrega la tarea al grupo de tareas para mantener seguimiento
                        processed_links[link] = task  # Asocia el enlace con la tarea creada

        if tasks:
            await asyncio.gather(*tasks)  # Espera a que todas las tareas terminen

        logging.info("Verificación de enlaces completada. Esperando 60 segundos para la próxima verificación.")
        await asyncio.sleep(60)  # Espera 1 minuto antes de la siguiente verificación

# Define si el mensaje es un comando y si el bot ha sido mencionado
async def is_bot_mentioned(event):
    return event.is_private or event.message.mentioned

# Comando de inicio de monitoreo y grabación
@bot.on(events.NewMessage(pattern='/grabar'))
async def handle_grabar(event):
    if await is_bot_mentioned(event) and event.sender_id in AUTHORIZED_USERS:
        await event.respond(
            "🔴 <b>Inicia monitoreo y grabación automática de una transmisión</b> 🔴\n\n"
            "Por favor, envía la URL de la transmisión para comenzar.",
            parse_mode='html'
        )
        is_recording[event.sender_id] = True
        
    else:
        await event.respond("❗ No tienes permiso para usar este comando.")

# Comando para guardar enlaces
@bot.on(events.NewMessage)
async def save_link(event):
    # Ignorar mensajes que no sean comandos ni mencionen al bot
    if not await is_bot_mentioned(event) and not event.text.startswith('/'):
        return
    
    # Ignorar comandos que comienzan con '/' pero no son el comando actual
    if event.text.startswith('/') and event.text.split()[0] not in ['/grabar', '/start', '/mis_enlaces', '/eliminar_enlace', '/status']:
        return
    
    # Procesar solo si el usuario está autorizado
    if event.sender_id in AUTHORIZED_USERS:
        if is_valid_url(event.text):
            add_link(event.sender_id, event.text)
            await event.respond("✅ Enlace guardado para grabación.")
        else:
            await event.respond("❌ URL no válida. Por favor, envía una URL válida.")
    else:
        await event.respond("❗ No tienes permiso para guardar enlaces.")

# Comando para mostrar enlaces guardados
@bot.on(events.NewMessage(pattern='/mis_enlaces'))
async def show_links(event):
    if await is_bot_mentioned(event):
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

@bot.on(events.NewMessage(pattern='/estado_grabacion'))
async def check_recording_status(event):
    if event.sender_id in is_recording:
        status = "en modo grabación" if is_recording[event.sender_id] else "no en modo grabación"
        await event.respond(f"📹 Actualmente estás {status}.")
    else:
        await event.respond("❗ No tienes un estado de grabación establecido.")

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
    await event.respond("⚠️ Comando no reconocido. Usa /grabar, /mis_enlaces, /eliminar_enlace o /status.")

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
        "• <b>/eliminar_enlace</b> - Elimina un enlace guardado.\n"
        "• <b>/status</b> - Muestra el estado del bot.\n",
        parse_mode='html'
    )

if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    
    bot.loop.create_task(verificar_enlaces())  # Lanza la verificación en paralelo
    bot.run_until_disconnected()
    driver.quit()
