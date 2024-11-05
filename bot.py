import subprocess
import time
import os
import logging
import glob
import json
from collections import defaultdict
from telethon import TelegramClient, events, Button
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse

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
MAX_TELEGRAM_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB en bytes

AUTHORIZED_USERS = {1170684259, 1218594540}
is_recording = {}  # Diccionario para almacenar el estado de grabación por usuario

# Diccionario para almacenar información de grabación por modelo
grabaciones = {}

# Cargar y guardar enlaces
def load_links():
    """Carga los enlaces desde un archivo JSON."""
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_links(links):
    """Guarda los enlaces en un archivo JSON."""
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

def setup_driver():
    # Inicializa el navegador
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")  # Evita el sandbox cuando se ejecuta como root
    chrome_options.add_argument("--headless")  # Ejecuta sin interfaz gráfica
    chrome_options.add_argument("--disable-dev-shm-usage")  # Usa /tmp en lugar de /dev/shm para memoria compartida
    chrome_options.add_argument("--remote-debugging-port=9222")  # Habilita un puerto para depuración remota

    # Crea el driver de Chrome
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)
    return driver

async def extract_last_m3u8_link(driver, chaturbate_link):
    try:
        # Navegar a la página de extracción de m3u8
        driver.get("https://onlinetool.app/ext/m3u8_extractor")
        
        # Esperar a que el campo de entrada esté disponible y enviar el enlace
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "url"))
        )
        input_field.clear()
        input_field.send_keys(chaturbate_link)

        # Esperar y hacer clic en el botón "Run"
        run_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[span[text()="Run"]]'))
        )
        run_button.click()
        logging.info("Botón 'Run' clickeado, esperando a que se procesen los enlaces...")

        # Esperar a que los enlaces m3u8 se generen y estén disponibles
        m3u8_links = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, '//pre/a'))
        )

        # Obtener el último enlace m3u8 si existe
        if m3u8_links:
            last_m3u8_link = m3u8_links[-1].get_attribute('href')
            logging.info(f"Enlace m3u8 extraído: {last_m3u8_link}")
            return last_m3u8_link
        else:
            logging.warning("No se encontraron enlaces m3u8.")
            return None
    except Exception as e:
        logging.error(f"Error al extraer el enlace: {e}")
        return None

async def upload_and_delete_mp4_files(user_id, chat_id):
    try:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        
        for file in files:
            file_path = os.path.join(DOWNLOAD_PATH, file)
            command = ["rclone", "copy", file_path, GDRIVE_PATH]
            
            # Ejecutar el proceso de subida a Google Drive
            try:
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=300
                )
            except asyncio.TimeoutError:
                logging.error(f"Timeout al intentar subir el archivo: {file}")
                await bot.send_message(user_id, f"❌ Timeout al intentar subir el archivo: {file}")
                continue
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logging.info(f"Subida exitosa: {file}")

                # Crear enlace compartido
                try:
                    share_process = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            "rclone", "link", GDRIVE_PATH + file,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        ),
                        timeout=300
                    )
                except asyncio.TimeoutError:
                    logging.error(f"Timeout al intentar crear el enlace compartido para el archivo: {file}")
                    await bot.send_message(user_id, f"❌ Timeout al intentar crear el enlace compartido para: {file}")
                    continue
                share_stdout, share_stderr = await share_process.communicate()
                
                if share_process.returncode == 0:
                    shared_link = share_stdout.strip().decode('utf-8')
                    await bot.send_message(user_id, f"✅ Video subido: {file}\n🔗 Enlace: {shared_link}")  # Envío por privado
                else:
                    logging.error(f"Error al crear enlace compartido para {file}: {share_stderr.decode('utf-8')}")
                    await bot.send_message(user_id, f"❌ Error al crear enlace compartido para: {file}")  # Notificar al usuario
            else:
                logging.error(f"Error al subir {file}: {stderr.decode('utf-8')}")
                await bot.send_message(user_id, f"❌ Error al subir el archivo: {file}")
                continue
            
            # Envío del video al chat de Telegram
            if os.path.getsize(file_path) <= MAX_TELEGRAM_SIZE:
                await bot.send_file(chat_id, file_path, caption=f"📹 Video: {file}")
            else:
                await send_large_file_stream(chat_id, file_path)
            
            # Eliminar archivo local tras envío exitoso
            os.remove(file_path)
            logging.info(f"Archivo eliminado: {file}")

    except Exception as e:
        logging.error(f"Error en la función upload_and_delete_mp4_files: {e}")
        await bot.send_message(user_id, f"❌ Error en el proceso de subida y eliminación: {e}")

async def send_large_file_stream(chat_id, file_path):
    try:
        file_size = os.path.getsize(file_path)
        chunk_size = 10 * 1024 * 1024  # 10 MB
        with open(file_path, 'rb') as f:
            part_num = 1
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                await bot.send_file(chat_id, chunk, caption=f"📹 Parte {part_num}", file_name=f"{os.path.basename(file_path)}.part{part_num}")
                part_num += 1
    except Exception as e:
        logging.error(f"Error al enviar el archivo en partes: {e}")

async def download_with_yt_dlp(m3u8_url, user_id, modelo, original_link, chat_id):
    fecha_hora = time.strftime("%Y%m%d_%H%M%S")
    output_file_path = os.path.join(DOWNLOAD_PATH, f"{modelo}_{fecha_hora}.mp4")
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', output_file_path]
    
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url} para {modelo}")
        await bot.send_message(chat_id, f"🔴 Iniciando grabación: {original_link}")

        grabaciones[modelo] = {
            'inicio': time.time(),
            'file_path': output_file_path,
            'user_id': user_id,
        }

        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *command_yt_dlp,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=600
            )
        except asyncio.TimeoutError:
            logging.error(f"Timeout al intentar descargar el archivo para: {modelo}")
            await bot.send_message(chat_id, f"❌ Timeout al intentar descargar el archivo para: {modelo}")
            return

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logging.info(f"Descarga completa para {modelo}.")
            await bot.send_message(chat_id, f"✅ Grabación completa para {modelo}.")
            await upload_and_delete_mp4_files(user_id, chat_id)
        else:
            stderr = stderr.decode('utf-8')
            logging.error(f"Error al descargar para {modelo}: {stderr}")
            await bot.send_message(chat_id, f"❌ Error al descargar para {modelo}: {stderr}")
    except Exception as e:
        logging.error(f"Error durante la descarga para {modelo}: {e}")
        await bot.send_message(chat_id, f"❌ Error durante la descarga para {modelo}: {e}")
    finally:
        grabaciones.pop(modelo, None)

async def verificar_enlaces():
    driver = setup_driver()  # Asegúrate de que `setup_driver()` retorne un driver válido.
    while True:
        links = load_links()
        if not links:
            logging.warning("No se cargaron enlaces guardados.")
            await asyncio.sleep(60)
            continue

        tasks = []
        processed_links = {}

        for user_id_str, user_links in links.items():
            if not user_id_str or user_id_str == 'None':
                logging.error(f"user_id_str inválido: '{user_id_str}'. Verifica el origen de los enlaces guardados.")
                continue

            try:
                user_id = int(user_id_str)
            except ValueError as e:
                logging.error(f"Error de conversión a int para user_id_str '{user_id_str}': {e}")
                continue

            for link in user_links:
                if link not in processed_links:
                    m3u8_link = await extract_last_m3u8_link(driver, link)
                    if m3u8_link:
                        modelo = link.rstrip('/').split('/')[-1]

                        # Iniciar una nueva grabación sin detener procesos en curso
                        task = asyncio.create_task(download_with_yt_dlp(m3u8_link, user_id, modelo, link, user_id))
                        tasks.append(task)
                        processed_links[link] = task
                    else:
                        modelo = link.rstrip('/').split('/')[-1]
                        if modelo in grabaciones:
                            await alerta_emergente(modelo, 'offline', user_id)
                            grabaciones.pop(modelo, None)
                        logging.warning(f"No se pudo obtener un enlace m3u8 válido para el enlace: {link}")

        if tasks:
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                logging.error(f"Error durante la ejecución de tareas concurrentes: {e}")

        logging.info("Verificación de enlaces completada. Esperando 60 segundos para la próxima verificación.")
        await asyncio.sleep(60)

    driver.quit()  # Asegúrate de cerrar el driver cuando termines.

async def alerta_emergente(modelo, estado, user_id):
    if estado == 'online':
        info = grabaciones.get(modelo)
        if not info:
            mensaje_alerta = f"{modelo} está 🟢 online."
        else:
            tiempo_grabacion = time.time() - info['inicio']
            try:
                tamano_bytes = os.path.getsize(info['file_path'])
                tamano_MB = tamano_bytes / (1024 ** 2)
            except OSError as e:
                tamano_MB = 0
                logging.error(f"Error al obtener el tamaño del archivo para {modelo}: {e}")

            horas, resto = divmod(int(tiempo_grabacion), 3600)
            minutos, segundos = divmod(resto, 60)
            tiempo_formateado = f"{horas}h {minutos}m {segundos}s"

            mensaje_alerta = (
                f"{modelo} está 🟢 online.\n"
                f"En grabación: {tiempo_formateado}\n"
                f"Tamaño del video: {tamano_MB:.2f} MB"
            )
    else:
        mensaje_alerta = f"{modelo} está 🔴 offline."

    await bot.send_message(int(user_id), mensaje_alerta)

@bot.on(events.NewMessage(pattern='/check_modelo'))
async def check_modelo(event):
    if len(event.raw_text.split()) < 2:
        await event.respond("Por favor, proporciona el nombre de la modelo después del comando.")
        return

    nombre_modelo = event.raw_text.split()[1]
    buttons = [
        [Button.inline(f"Estado de {nombre_modelo}", data=f"alerta_modelo:{nombre_modelo}")]
    ]
    await event.respond("Haz clic en el botón para ver el estado de la modelo:", buttons=buttons)

@bot.on(events.CallbackQuery(data=lambda data: data.startswith(b"alerta_modelo")))
async def callback_alert(event):
    modelo_url = event.data.decode().split(':')[1]
    modelo = modelo_url.split('/')[-1]
    mensaje_alerta, _ = await obtener_informacion_modelo(modelo, event.sender_id)
    await event.answer(mensaje_alerta, alert=True)

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "👋 <b>¡Bot de Grabación Automática!</b>\n\n"
        "Puedes iniciar una grabación enviando una URL válida.\n"
        "Comandos:\n"
        "• <b>/grabar</b> - Inicia monitoreo y grabación automática de una transmisión.\n"
        "• <b>/mis_enlaces</b> - Muestra tus enlaces guardados.\n"
        "• <b>/eliminar_enlace</b> - Elimina un enlace guardado.\n"
        "• <b>/status</b> - Muestra el estado del bot.\n"
        "• <b>/check_modelo</b> - Verifica el estado de la modelo (online u offline)\n",
        parse_mode='html'
    )

if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    bot.loop.create_task(verificar_enlaces())
    bot.run_until_disconnected()
