import subprocess
import time
import os
import logging
import glob
import requests
import tempfile
from collections import defaultdict
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeVideo
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse
import json

# Cargar configuración desde config.json
with open("config.json", "r") as f:
    config = json.load(f)

API_ID = config.get("API_ID")
API_HASH = config.get("API_HASH")
BOT_TOKEN = config.get("BOT_TOKEN")

# Verificar si los valores necesarios están configurados
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("❌ Configuración incompleta en config.json. Asegúrate de definir API_ID, API_HASH y BOT_TOKEN.")

# Inicializar el bot
bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-gpu")  # Puede mejorar la estabilidad en headless
    chrome_options.add_argument("--window-size=1920,1080")  # Evita problemas de tamaño en headless

    try:
        driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)
        logging.info("ChromeDriver iniciado exitosamente.")
        return driver
    except Exception as e:
        logging.error(f"Error al iniciar ChromeDriver: {e}")
        return None

LINKS_FILE = 'links.json'
DOWNLOAD_PATH = "/root/cbautorec/"
GDRIVE_PATH = "gdrive:/182Bi69ovEbkvZAlcIYYf-pV1UCeEzjXH/"
MAX_TELEGRAM_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB en bytes
LOG_CHANNEL = "@logscbdl"
LOG_CLIPS_CHANNEL = "@clipscb"  # Nombre del canal donde se subirán los clips

ADMIN_ID = 1170684259  # ID del administrador autorizado
AUTHORIZED_USERS = {1170684259, 1218594540}
is_recording = {}  # Diccionario para almacenar el estado de grabación por usuario
pending_clips = {}  # Variable temporal para almacenar el estado del enlace en espera de cada usuario
grabaciones = {}  # Diccionario para almacenar información de grabación por modelo
active_downloads = set()  # Descargas activas

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

def add_link(user_id, link):
    """Agrega un enlace a la lista de un usuario."""
    links = load_links()
    user_id_str = str(user_id)
    if user_id_str not in links:
        links[user_id_str] = []
    if link not in links[user_id_str]:
        links[user_id_str].append(link)
        save_links(links)

def remove_link(user_id, link):
    """Elimina un enlace de la lista de un usuario."""
    links = load_links()
    user_id_str = str(user_id)
    if user_id_str in links and link in links[user_id_str]:
        links[user_id_str].remove(link)
        save_links(links)

def delete_link(link):
    """Elimina un enlace de la lista de enlaces global."""
    links = load_links()  # Cargar enlaces una sola vez
    # Recorre todos los usuarios para eliminar el enlace
    for user_links in links.values():
        if link in user_links:
            user_links.remove(link)
            save_links(links)  # Guardar los enlaces actualizados
            logging.info(f"Enlace eliminado: {link}")
            return f"Enlace eliminado: {link}"
    logging.warning(f"El enlace no existe: {link}")
    return "El enlace no existe."

# Validación de URL
def is_valid_url(url):
    """Valida si una URL es válida."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Extracción de enlace m3u8 con Selenium
async def extract_last_m3u8_link(driver, chaturbate_link):
    """
    Extrae el último enlace m3u8 de la página de extracción usando el driver proporcionado.
    """
    # Validar que el driver esté activo antes de proceder
    if driver is None:
        logging.error("ChromeDriver no se pudo iniciar. Extracción de enlace m3u8 fallida.")
        return None

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

async def get_video_metadata(file_path):
    # Ejecuta ffprobe para obtener la metadata del video
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,duration', '-of', 'default=noprint_wrappers=1', file_path
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    # Extrae los valores de la salida
    if process.returncode == 0:
        output = stdout.decode().splitlines()
        width, height, duration = None, None, None
        for line in output:
            if line.startswith("width="):
                width = int(line.split("=")[1])
            elif line.startswith("height="):
                height = int(line.split("=")[1])
            elif line.startswith("duration="):
                duration = int(float(line.split("=")[1]))
        return duration, width, height
    else:
        logging.error(f"Error obteniendo metadata de video: {stderr.decode()}")
        return None, None, None
        
# Subprocesos asincrónicos para FFmpeg y ffprobe
async def run_ffmpeg_command(command):
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    return stdout, stderr, process.returncode
    
async def upload_and_delete_mp4_files(user_id, chat_id):
    try:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        tasks = []

        for file in files:
            file_path = os.path.join(DOWNLOAD_PATH, file)
            # Verificar que el archivo existe antes de intentar la carga
            if os.path.exists(file_path):
                task = asyncio.create_task(upload_and_notify(user_id, chat_id, file))
                tasks.append(task)

                # Configurar la eliminación del archivo después de subirlo
                task.add_done_callback(lambda t, path=file_path: os.remove(path) if os.path.exists(path) else None)
            else:
                logging.warning(f"El archivo {file} no existe y no se puede cargar.")

        # Ejecutar todas las tareas en paralelo y esperar a que terminen
        await asyncio.gather(*tasks)

    except Exception as e:
        logging.error(f"Error en la función upload_and_delete_mp4_files: {e}")
        await bot.send_message(user_id, f"❌ Error en el proceso de subida y eliminación: {e}")

# Función para enviar mensaje al canal cuando se inicia la grabación
async def notify_recording_start(modelo, link, user_id):
    message = (
        f"📡 <b>Inicio de Grabación</b>\n\n"
        f"🔗 <b>Modelo:</b> {modelo}\n"
        f"🌐 <b>Link:</b> {link}\n"
        f"👤 <b>ID Usuario:</b> {user_id}"
    )
    await bot.send_message(LOG_CHANNEL, message, parse_mode="html")

async def upload_and_notify(user_id, chat_id, file_path):
    """
    Función para cargar un archivo a Google Drive y notificar en Telegram.
    Esto se ejecuta en paralelo sin bloquear la verificación de enlaces.
    """
    # Llamada a la función de manejo de subida que ya tienes configurada
    await handle_file_upload(user_id, chat_id, file_path)

    # Opcional: enviar mensaje adicional de confirmación si necesitas
    logging.info(f"Subida y notificación completadas para {file_path}")

async def handle_file_upload(user_id, chat_id, file):
    file_path = os.path.join(DOWNLOAD_PATH, file)
    command = ["rclone", "copy", file_path, GDRIVE_PATH]

    try:
        if not os.path.exists(file_path):
            await bot.send_message(user_id, f"❌ El archivo {file} no existe o fue movido.")
            return

        # Subida a Google Drive
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logging.info(f"Subida exitosa: {file}")

            # Crear enlace compartido
            share_command = ["rclone", "link", GDRIVE_PATH + file]
            share_process = await asyncio.create_subprocess_exec(
                *share_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            share_stdout, share_stderr = await share_process.communicate()
            
            if share_process.returncode == 0:
                shared_link = share_stdout.strip().decode('utf-8')
                await bot.send_message(user_id, f"✅ Video subido: {file}\n🔗 Enlace: {shared_link}")

                # Notificación al canal de logs
                await bot.send_message(
                    LOG_CHANNEL,
                    f"✅ <b>Video Subido</b>\n\n📹 <b>Archivo:</b> {file}\n"
                    f"🔗 <b>Enlace:</b> {shared_link}",
                    parse_mode="html"
                )
            else:
                logging.error(f"Error al crear enlace compartido para {file}: {share_stderr.decode('utf-8')}")
                await bot.send_message(user_id, f"❌ Error al crear enlace compartido para: {file}")
        else:
            logging.error(f"Error al subir {file}: {stderr.decode('utf-8')}")
            await bot.send_message(user_id, f"❌ Error al subir el archivo: {file}")
            return

        # Obtener duración y dimensiones del video
        duration, width, height = await get_video_metadata(file_path)
        if duration is None or width is None or height is None:
            await bot.send_message(user_id, f"❌ Error al obtener metadatos del archivo: {file}")
            return

        # Generar una miniatura temporal de forma rápida
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_thumb:
            thumbnail_path = temp_thumb.name

        thumbnail_command = [
            "ffmpeg", "-y", "-i", file_path, "-ss", "00:00:01.000", "-vframes", "1", "-qscale:v", "2", thumbnail_path
        ]

        try:
            thumbnail_process = await asyncio.create_subprocess_exec(
                *thumbnail_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await thumbnail_process.communicate()
            logging.info("Miniatura generada exitosamente")
        except Exception as e:
            logging.error(f"Error al generar la miniatura: {e}")
            await bot.send_message(user_id, "⚠️ No se pudo generar la miniatura.")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            return

        # Envío del video a Telegram con soporte para streaming y miniatura
        if os.path.getsize(file_path) <= MAX_TELEGRAM_SIZE:
            await bot.send_file(
                chat_id, 
                file_path, 
                caption=f"📹 Video: {file}",
                thumb=thumbnail_path,
                attributes=[DocumentAttributeVideo(
                    duration=duration,
                    w=width,
                    h=height,
                    supports_streaming=True
                )]
            )
        else:
            await send_large_file(chat_id, file_path, bot)
        
        # Eliminar archivo de miniatura y archivo de video tras envío
        os.remove(thumbnail_path)
        os.remove(file_path)
        logging.info(f"Archivo eliminado: {file}")

    except Exception as e:
        logging.error(f"Error en la función handle_file_upload para {file}: {e}")
        await bot.send_message(user_id, f"❌ Error en el proceso de subida y eliminación para {file}: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)

import os
import tempfile
import logging
import asyncio
from telethon.tl.types import DocumentAttributeVideo

async def send_large_file(chat_id, file_path, bot):
    # Obtain the total duration of the video file
    command_ffprobe = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    process = await asyncio.create_subprocess_exec(
        *command_ffprobe,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    try:
        total_duration = float(stdout.decode().strip())
    except ValueError as e:
        logging.error(f"Error al obtener duración del archivo {file_path}: {e}")
        await bot.send_message(chat_id, "❌ No se pudo obtener la duración del archivo.")
        return
    
    part_duration = 60 * 30  # Split into 30-minute parts
    current_time = 0
    part_num = 1

    while current_time < total_duration:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            part_path = temp_file.name

        try:
            # Create each video segment with FFmpeg
            ffmpeg_command = [
                "ffmpeg", "-y", "-i", file_path, "-ss", str(current_time),
                "-t", str(part_duration), "-c", "copy", part_path
            ]
            process = await asyncio.create_subprocess_exec(*ffmpeg_command)
            await process.wait()

            if os.path.exists(part_path):
                # Obtain metadata for each part
                metadata_command = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,duration",
                    "-of", "default=noprint_wrappers=1", part_path
                ]
                meta_process = await asyncio.create_subprocess_exec(
                    *metadata_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                meta_stdout, meta_stderr = await meta_process.communicate()

                # Extract width, height, and duration values
                width, height, duration = None, None, None
                for line in meta_stdout.decode().splitlines():
                    if line.startswith("width="):
                        width = int(line.split("=")[1])
                    elif line.startswith("height="):
                        height = int(line.split("=")[1])
                    elif line.startswith("duration="):
                        duration = int(float(line.split("=")[1]))

                # Generate a thumbnail for each part
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_thumb:
                    thumbnail_path = temp_thumb.name
                
                thumbnail_command = [
                    "ffmpeg", "-y", "-i", part_path, "-ss", "00:00:01.000", 
                    "-vframes", "1", "-qscale:v", "2", thumbnail_path
                ]
                thumb_process = await asyncio.create_subprocess_exec(*thumbnail_command)
                await thumb_process.wait()

                # Send the part with thumbnail and metadata to Telegram
                await bot.send_file(
                    chat_id,
                    part_path,
                    caption=f"📹 Parte {part_num}",
                    thumb=thumbnail_path,
                    attributes=[DocumentAttributeVideo(
                        duration=duration,
                        w=width,
                        h=height,
                        supports_streaming=True
                    )]
                )

                # Remove the thumbnail and part files after sending
                os.remove(thumbnail_path)
                os.remove(part_path)
            else:
                await bot.send_message(chat_id, "❌ Error al crear la parte del archivo.")
                break

            current_time += part_duration
            part_num += 1

        except Exception as e:
            logging.error(f"Error durante la división y envío de archivo: {e}")
            await bot.send_message(chat_id, f"❌ Error al dividir/enviar el archivo: {e}")
            break

async def download_with_yt_dlp(m3u8_url, user_id, modelo, original_link, chat_id):
    fecha_hora = time.strftime("%Y%m%d_%H%M%S")
    output_file_path = os.path.join(DOWNLOAD_PATH, f"{modelo}_{fecha_hora}.mp4")
    command_yt_dlp = ['yt-dlp', m3u8_url, '-o', output_file_path]  # Omitimos -f best

    # Mensajes de inicio de descarga
    logging.info(f"Descarga iniciada con yt-dlp para {modelo}")
    await bot.send_message(chat_id, f"🔴 Iniciando grabación: {original_link}")
    await bot.send_message(chat_id, f"🎬 Enlace para grabar clips de {modelo}: {m3u8_url}")

    # Inicializar `process` en None para evitar problemas de referencia
    process = None

    try:
        # Ejecutar yt-dlp como subproceso asincrónico
        process = await asyncio.create_subprocess_exec(
            *command_yt_dlp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Almacenar el proceso en `grabaciones` solo si el proceso se inicia correctamente
        grabaciones[modelo] = {
            'inicio': time.time(),
            'file_path': output_file_path,
            'user_id': user_id,
            'm3u8_url': m3u8_url,
            'chats': {chat_id},
            'process': process  # Guardar el proceso aquí
        }

        # Capturar salida y errores del proceso
        stdout, stderr = await process.communicate()

        # Verificar que el archivo se haya descargado correctamente
        if process.returncode == 0 and os.path.exists(output_file_path):
            file_size = os.path.getsize(output_file_path) / (1024 ** 2)
            logging.info(f"Descarga completa para {modelo}. Tamaño del archivo: {file_size:.2f} MB")
            for chat in grabaciones[modelo]['chats']:
                await bot.send_message(chat, f"✅ Grabación completa para {modelo}. Tamaño del archivo: {file_size:.2f} MB")
            await upload_and_delete_mp4_files(user_id, chat_id)
        else:
            error_msg = (
                f"❌ Error en la descarga de {modelo}. "
                f"Código de retorno: {process.returncode}\n"
                f"Salida de error: {stderr.decode()}"
            )
            logging.error(error_msg)
            for chat in grabaciones[modelo]['chats']:
                await bot.send_message(chat, error_msg)
            # Eliminamos de `grabaciones` si falla
            grabaciones.pop(modelo, None)

    except Exception as e:
        logging.error(f"Excepción durante la descarga de {modelo}: {e}")
        for chat in grabaciones[modelo]['chats']:
            await bot.send_message(chat, f"❌ Excepción en la descarga para {modelo}: {e}")
        # Eliminamos de `grabaciones` si falla
        grabaciones.pop(modelo, None)

    finally:
        # Aseguramos que el archivo se elimine si la descarga falló
        if process is not None and os.path.exists(output_file_path) and process.returncode != 0:
            logging.info(f"Eliminando archivo incompleto: {output_file_path}")
            os.remove(output_file_path)

        # Limpiar grabaciones si no hay chats registrados para la descarga
        if modelo in grabaciones and not grabaciones[modelo]['chats']:
            grabaciones.pop(modelo, None)

# Función para obtener la información de la modelo
async def obtener_informacion_modelo(modelo, user_id):
    info = grabaciones.get(modelo)
    if not info:
        return f"{modelo} está 🔴 offline.", False

    estado = "🟢 online"
    tiempo_grabacion = time.time() - info['inicio']
    
    # Buscar el archivo de la grabación en curso con extensión .mp4.part
    archivo_en_grabacion = glob.glob(f"{info['file_path']}.part")
    
    # Inicializar el tamaño del archivo a 0 MB
    tamano_MB = 0

    try:
        if archivo_en_grabacion:
            # Si el archivo .part existe, obtener su tamaño
            tamano_bytes = os.path.getsize(archivo_en_grabacion[0])
            tamano_MB = tamano_bytes / (1024 ** 2)
        else:
            # Si no existe el archivo .part, verificar si existe el archivo final
            if os.path.exists(info['file_path']):
                tamano_bytes = os.path.getsize(info['file_path'])
                tamano_MB = tamano_bytes / (1024 ** 2)
            else:
                logging.error(f"Archivo no encontrado: {info['file_path']}.part o {info['file_path']}")
                return f"{modelo} está online, pero el tamaño del archivo aún no está disponible.", True
    except OSError as e:
        logging.error(f"Error al obtener el tamaño del archivo para {modelo}: {e}")

    mensaje = (
        f"Modelo: {modelo}\n"
        f"Estado: {estado}\n"
        f"Tiempo de grabación: {int(tiempo_grabacion // 60)} min\n"
        f"Tamaño del video: {tamano_MB:.2f} MB"
    )
    
    return mensaje, True

# Función para enviar el mensaje con la lista de botones para cada modelo en grabación
@bot.on(events.NewMessage(pattern='/check_modelo'))
async def check_modelo(event):
    user_id = event.sender_id

    # Filtrar modelos en grabación específicos para el usuario
    modelos_usuario = [
        modelo for modelo, info in grabaciones.items() if info['user_id'] == user_id
    ]

    # Verificar si el usuario tiene grabaciones activas
    if not modelos_usuario:
        await event.respond("📡 Actualmente no tienes modelos en grabación.")
        return

    # Crear una lista de botones para cada modelo que el usuario está grabando
    buttons = [
        [Button.inline(f"📍 {modelo}", data=f"alerta_modelo:{modelo}")]
        for modelo in modelos_usuario
    ]
    
    # Mensaje de bienvenida y guía
    mensaje = (
        "📋 <b>Modelos en Grabación</b>\n\n"
        "Selecciona un modelo de la lista para ver su estado actual.\n"
        "Cada modelo muestra su progreso de grabación y el tamaño del archivo actual.\n"
    )
    
    # Enviar el mensaje con los botones
    await event.respond(mensaje, buttons=buttons, parse_mode='html')
    
# Función que recibe el callback del botón y muestra una alerta con el estado del modelo
@bot.on(events.CallbackQuery(data=lambda data: data.startswith(b"alerta_modelo")))
async def callback_alert(event):
    # Extrae el nombre del modelo desde el callback data
    modelo = event.data.decode().split(':')[1]

    # Obtener el estado actual del modelo
    mensaje_alerta, online = await obtener_informacion_modelo(modelo, event.sender_id)

    # Enviar el mensaje como una alerta emergente
    await event.answer(mensaje_alerta, alert=True)
    
# Driver inicializado fuera de la función para reutilización global
driver = None

async def verificar_enlaces():
    global driver  # Reutilizar el driver globalmente
    if driver is None:
        driver = setup_driver()  # Inicializa el driver si aún no está configurado

    while driver is not None:
        try:
            links = load_links()
            if not links:
                logging.warning("No se cargaron enlaces guardados.")
                await asyncio.sleep(60)
                continue

            tasks = []
            processed_links = {}

            for user_id_str, user_links in links.items():
                try:
                    user_id = int(user_id_str)
                except ValueError as e:
                    logging.error(f"Error de conversión para user_id_str '{user_id_str}': {e}")
                    continue

                for link in user_links:
                    if link not in processed_links:
                        # Crear una tarea para procesar el enlace usando el mismo driver
                        task = asyncio.create_task(process_link(driver, user_id, link))
                        tasks.append(task)
                        processed_links[link] = task

            if tasks:
                await asyncio.gather(*tasks)  # Ejecuta todas las tareas en paralelo

        except Exception as e:
            logging.error(f"Error en el ciclo de verificación: {e}")
            if driver:
                driver.quit()  # Cierra el driver en caso de error crítico
                driver = None  # Marca el driver como no inicializado

            # Reinstancia el driver después de un error
            driver = setup_driver()

        else:
            logging.info("Verificación de enlaces completada. Esperando 60 segundos para la próxima verificación.")

        await asyncio.sleep(60)  # Espera antes de la próxima verificación

    # Asegura que el driver se cierre correctamente al finalizar el ciclo
    if driver:
        driver.quit()
        driver = None

# Procesa cada enlace usando el mismo driver
async def process_link(driver, user_id, link):
    m3u8_link = await extract_last_m3u8_link(driver, link)
    if m3u8_link:
        modelo = link.rstrip('/').split('/')[-1]  # Extrae el nombre del modelo

        # Verificar si ya hay una grabación activa para este modelo y enlace m3u8
        if modelo in grabaciones and grabaciones[modelo].get('m3u8_url') == m3u8_link:
            logging.info(f"Grabación ya activa para {modelo}. Compartiendo progreso.")
            grabaciones[modelo]['chats'].add(user_id)  # Agregar chat para compartir progreso
            await alerta_emergente(modelo, 'online', user_id)
        else:
            # Iniciar una nueva grabación y registrar en grabaciones activas
            await download_with_yt_dlp(m3u8_link, user_id, modelo, link, user_id)
    else:
        # Notificar estado offline si el enlace m3u8 no se pudo obtener
        modelo = link.rstrip('/').split('/')[-1]
        if modelo in grabaciones:
            await alerta_emergente(modelo, 'offline', user_id)
            grabaciones.pop(modelo, None)
        logging.warning(f"No se pudo obtener un enlace m3u8 válido para el enlace: {link}")

# Función para enviar alertas emergentes
async def alerta_emergente(modelo, estado, user_id):
    if estado == 'online':
        info = grabaciones.get(modelo)
        if not info:
            mensaje_alerta = f"{modelo} está 🟢 online."
        else:
            tiempo_grabacion = time.time() - info['start_time']
            try:
                tamano_bytes = os.path.getsize(info['file_path'])
                tamano_MB = tamano_bytes / (1024 ** 2)
            except OSError as e:
                tamano_MB = 0
                logging.error(f"Error al obtener el tamaño del archivo para {modelo}: {e}")

            # Formatear el tiempo de grabación
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

    # Mostrar la alerta emergente
    await bot.send_message(int(user_id), mensaje_alerta)

# Define si el mensaje es un comando y si el bot ha sido mencionado
async def is_bot_mentioned(event):
    return event.is_private or event.message.mentioned

# Comando para revisar y detener grabaciones activas
@bot.on(events.NewMessage(pattern='/check_grabaciones'))
async def check_grabaciones(event):
    user_id = event.sender_id

    # Verificar si el usuario está autorizado
    if user_id not in AUTHORIZED_USERS:
        await event.respond("❌ No tienes permiso para usar este comando.")
        return

    # Filtrar modelos en grabación específicos para el usuario
    modelos_usuario = [
        modelo for modelo, info in grabaciones.items() if info['user_id'] == user_id
    ]

    # Verificar si el usuario tiene grabaciones activas
    if not modelos_usuario:
        await event.respond("📡 Actualmente no tienes grabaciones activas.")
        return

    # Crear una lista de botones "Detener" para cada modelo que el usuario está grabando
    buttons = [
        [Button.inline(f"🛑 Detener {modelo}", data=f"stop_recording:{modelo}")]
        for modelo in modelos_usuario
    ]
    
    # Mensaje de bienvenida y guía
    mensaje = (
        "📋 <b>Grabaciones Activas</b>\n\n"
        "Selecciona una grabación de la lista para detenerla y procesarla.\n"
        "Al detener, el video se procesará y se subirá a Google Drive y Telegram.\n"
    )
    
    # Enviar el mensaje con los botones
    await event.respond(mensaje, buttons=buttons, parse_mode='html')

# Modificar la función `stop_recording` para detener el proceso y procesar el archivo `.part`
@bot.on(events.CallbackQuery(data=lambda data: data.startswith(b"stop_recording")))
async def stop_recording(event):
    modelo = event.data.decode().split(':')[1]
    user_id = event.sender_id

    # Verificar si el modelo está en grabación activa
    if modelo in grabaciones:
        await event.answer(f"🛑 Deteniendo grabación de {modelo}...")
        
        # Detener el proceso de descarga
        grab_info = grabaciones[modelo]
        process = grab_info.get('process')
        
        if process:
            process.terminate()  # Detener el proceso
            await process.wait()  # Esperar a que se cierre completamente
        
        # Procesar el archivo .part
        part_file_path = f"{grab_info['file_path']}.part"
        file_path = grab_info['file_path']
        
        # Si el archivo .part existe, renombrarlo a archivo final
        if os.path.exists(part_file_path):
            os.rename(part_file_path, file_path)
        
        # Procesar el archivo renombrado o el archivo final existente
        await process_and_upload_video(user_id, event.chat_id, file_path, modelo)
        
        # Limpiar la información de grabación
        grabaciones.pop(modelo, None)
    else:
        await event.answer(f"No se encontró una grabación activa para {modelo}.", alert=True)

async def process_and_upload_video(user_id, chat_id, file_path, modelo):
    # Comando ffprobe para obtener metadatos de duración y dimensiones
    metadata_command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "default=noprint_wrappers=1", file_path
    ]
    meta_process = await asyncio.create_subprocess_exec(
        *metadata_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    meta_stdout, meta_stderr = await meta_process.communicate()

    # Extraer valores de ancho, alto y duración
    width, height, duration = None, None, None
    for line in meta_stdout.decode().splitlines():
        if line.startswith("width="):
            width = int(line.split("=")[1])
        elif line.startswith("height="):
            height = int(line.split("=")[1])
        elif line.startswith("duration="):
            duration = int(float(line.split("=")[1]))

    # Generar una miniatura del video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_thumb:
        thumbnail_path = temp_thumb.name

    thumbnail_command = [
        "ffmpeg", "-y", "-i", file_path, "-ss", "00:00:01.000",
        "-vframes", "1", "-qscale:v", "2", thumbnail_path
    ]
    thumb_process = await asyncio.create_subprocess_exec(*thumbnail_command)
    await thumb_process.wait()

    # Subir el video a Google Drive
    await upload_to_gdrive(file_path, modelo)

    # Enviar el video a Telegram con soporte de streaming y miniatura
    if os.path.getsize(file_path) <= MAX_TELEGRAM_SIZE:
        await bot.send_file(
            chat_id, 
            file_path, 
            caption=f"📹 Grabación de {modelo}",
            thumb=thumbnail_path,
            attributes=[DocumentAttributeVideo(
                duration=duration,
                w=width,
                h=height,
                supports_streaming=True
            )]
        )
    else:
        await send_large_file(chat_id, file_path, bot)

    # Limpiar archivos temporales y de video local
    os.remove(thumbnail_path)
    os.remove(file_path)

async def upload_to_gdrive(file_path, modelo):
    # Subir el archivo a Google Drive con rclone
    command = ["rclone", "copy", file_path, GDRIVE_PATH]
    process = await asyncio.create_subprocess_exec(*command)
    await process.wait()

    # Generar enlace compartido de Google Drive
    share_command = ["rclone", "link", GDRIVE_PATH + os.path.basename(file_path)]
    share_process = await asyncio.create_subprocess_exec(
        *share_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    share_stdout, _ = await share_process.communicate()

    # Enviar el enlace de Google Drive al canal de log
    shared_link = share_stdout.decode().strip()
    await bot.send_message(
        LOG_CHANNEL,
        f"✅ <b>Video Subido</b>\n\n📹 <b>Modelo:</b> {modelo}\n"
        f"🔗 <b>Enlace:</b> {shared_link}",
        parse_mode="html"
    )

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

    # Procesar solo si el usuario está autorizado
    if event.sender_id not in AUTHORIZED_USERS:
        logging.warning(f"Intento de guardar enlace no autorizado por el usuario: {event.sender_id}")
        await event.respond("❗ No tienes permiso para guardar enlaces.")
        return

    # Ignorar comandos que comienzan con '/' pero no son el comando actual
    if event.text.startswith('/') and event.text.split()[0] not in ['/grabar', '/start', '/mis_enlaces', '/eliminar_enlace', '/status']:
        return
    
    # Ignorar enlaces que terminan en .m3u8
    if event.text.endswith('.m3u8'):
        logging.info("Enlace .m3u8 detectado y omitido.")
        warning_message = await event.respond("⚠️ Enlace de tipo `.m3u8` detectado y omitido para grabación general.")
        await asyncio.sleep(5)  # Espera 5 segundos antes de eliminar el mensaje
        await warning_message.delete()
        return
    
    # Guardar el enlace si es válido
    if is_valid_url(event.text):
        add_link(event.sender_id, event.text)
        await event.respond("✅ Enlace guardado para grabación.")
    else:
        # No respondas nada si la URL es inválida
        return

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

# Comando para mostrar el estado del bot y del driver
@bot.on(events.NewMessage(pattern='/status'))
async def show_status(event):
    global driver  # Accede al driver global
    if driver is not None:
        try:
            # Verificar que el driver esté funcional haciendo una llamada básica
            driver.title  # Intentar acceder a una propiedad para confirmar que no está cerrado
            driver_status = "🟢 El driver de Selenium está funcionando correctamente."
        except Exception as e:
            driver_status = f"🔴 El driver de Selenium no está funcional: {e}"
    else:
        driver_status = "🔴 El driver de Selenium no está inicializado."

    # Respuesta general del bot
    await event.respond(
        f"✅ El bot está en funcionamiento.\n\n{driver_status}"
    )

@bot.on(events.NewMessage(pattern='/estado_grabacion'))
async def check_recording_status(event):
    if event.sender_id in is_recording:
        status = "en modo grabación" if is_recording[event.sender_id] else "no en modo grabación"
        await event.respond(f"📹 Actualmente estás {status}.")
    else:
        await event.respond("❗ No tienes un estado de grabación establecido.")

def is_valid_url(url):
    # Verificar si la URL es válida (puedes personalizar esta función)
    return url.startswith("http://") or url.startswith("https://")

@bot.on(events.NewMessage(pattern='/clip'))
async def start_clip(event):
    await event.reply(
        "⚠️ Grabación de clips en <b>fase Beta</b>. Envía el enlace del stream para grabar un clip de 30 segundos.",
        parse_mode='html'
    )
    pending_clips[event.sender_id] = True

@bot.on(events.NewMessage)
async def process_clip_link(event):
    if event.sender_id in pending_clips and pending_clips[event.sender_id]:
        url = event.text.strip()

        # Validar si es un enlace válido
        if not is_valid_url(url):
            logging.warning(f"Enlace inválido ignorado: {url}")
            del pending_clips[event.sender_id]  # Eliminar el estado de clip pendiente
            return

        # Extraer el nombre del modelo del enlace
        try:
            modelo = url.split('amlst:')[1].split('-')[0]  # Extraer lo que está después de 'amlst:' y antes de '-'
        except IndexError:
            modelo = "Modelo_Desconocido"

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{DOWNLOAD_PATH}{modelo}_{timestamp}_clip.mp4"
        progress_message = await event.reply("⏳ Grabando clip de 30 segundos...")

        # Comando para grabar el clip de 30 segundos usando FFmpeg
        record_command = [
            "ffmpeg", "-y", "-i", url, "-t", "30", 
            "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", 
            "-c:a", "aac", "-b:a", "128k", filename
        ]

        # Ejecutar la grabación
        process = await asyncio.create_subprocess_exec(*record_command)

        # Ruta para la miniatura temporal
        thumbnail_path = f"{DOWNLOAD_PATH}{modelo}_{timestamp}_thumb.jpg"

        try:
            # Generar previews cada 5 segundos
            for i in range(5, 31, 5):  # Actualizar cada 5 segundos
                await asyncio.sleep(5)

                # Capturar un frame como miniatura a los `i` segundos
                thumbnail_command = [
                    "ffmpeg", "-y", "-i", url, "-ss", str(i), "-vframes", "1", 
                    "-q:v", "2", thumbnail_path
                ]
                thumbnail_process = await asyncio.create_subprocess_exec(*thumbnail_command)
                await thumbnail_process.wait()

                if os.path.exists(thumbnail_path):
                    # Actualizar el mensaje con la miniatura
                    await progress_message.edit(
                        f"⏳ Grabando clip... {i} segundos",
                        file=thumbnail_path
                    )
                    os.remove(thumbnail_path)  # Eliminar la miniatura después de usarla

        except Exception as e:
            logging.error(f"Error durante la generación de previews: {e}")
            await progress_message.edit("⚠️ Error al actualizar el progreso con previews.")

        # Esperar a que el proceso de grabación termine
        await process.wait()

        if process.returncode != 0:
            await progress_message.edit("❌ Error durante la grabación del clip.")
            del pending_clips[event.sender_id]
            return

        # Preparar información adicional
        perfil_url = f"https://chaturbate.com/{modelo}/"
        fecha_hora = time.strftime("%d/%m/%Y %H:%M:%S")

        # Enviar el clip al usuario
        await progress_message.edit("✅ Grabación completada. Enviando el clip...")
        await bot.send_file(
            event.chat_id, filename,
            caption=(
                f"🎬 <b>Clip grabado</b>\n\n"
                f"👤 <b>Modelo:</b> {modelo}\n"
                f"🕒 <b>Fecha y Hora:</b> {fecha_hora}\n"
                f"🌐 <b>Perfil:</b> <a href='{perfil_url}'>{perfil_url}</a>"
            ),
            parse_mode='html'
        )

        # Enviar el clip al canal de logs
        log_message = (
            f"🎥 <b>Nuevo Clip Grabado</b>\n\n"
            f"👤 <b>Modelo:</b> {modelo}\n"
            f"🕒 <b>Fecha y Hora:</b> {fecha_hora}\n"
            f"🌐 <b>Perfil:</b> <a href='{perfil_url}'>{perfil_url}</a>"
        )
        await bot.send_file(LOG_CLIPS_CHANNEL, filename, caption=log_message, parse_mode='html')

        # Limpiar después de enviar
        os.remove(filename)
        del pending_clips[event.sender_id]

# Comando para el administrador: Eliminar archivos .part y .mp4, y reiniciar el driver
@bot.on(events.NewMessage(pattern='/admin_reset'))
async def admin_reset(event):
    # Verifica si el comando fue enviado por el administrador
    if event.sender_id != ADMIN_ID:
        await event.respond("❌ No tienes permiso para ejecutar este comando.")
        return

    # Elimina únicamente archivos .part y .mp4 en el directorio de descargas
    try:
        deleted_files = []  # Mantener registro de los archivos eliminados
        for file in os.listdir(DOWNLOAD_PATH):
            if file.endswith(".part") or file.endswith(".mp4"):
                file_path = os.path.join(DOWNLOAD_PATH, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_files.append(file)
        
        if deleted_files:
            await event.respond(f"✅ Se eliminaron los siguientes archivos:\n" + "\n".join(deleted_files))
        else:
            await event.respond("✅ No se encontraron archivos .part o .mp4 para eliminar.")
    except Exception as e:
        await event.respond(f"❌ Error eliminando archivos: {e}")
        return

    # Reiniciar el driver
    try:
        global driver
        if driver:
            driver.quit()  # Asegurar que el driver actual se cierra antes de reiniciarlo
            driver = None
        
        driver = setup_driver()  # Crear una nueva instancia del driver
        await event.respond("✅ Driver reiniciado exitosamente.")
    except Exception as e:
        await event.respond(f"❌ Error reiniciando el driver: {e}")
        
# Comando para resetear enlaces
@bot.on(events.NewMessage(pattern='/reset_links'))
async def reset_links(event):
    if event.sender_id != ADMIN_ID:  # Solo el admin puede usar este comando
        await event.respond("❗ No tienes permiso para usar este comando.")
        return

    if os.path.exists(LINKS_FILE):
        os.remove(LINKS_FILE)
        await event.respond("✅ Enlaces reseteados exitosamente.")
    else:
        await event.respond("⚠️ No se encontró el archivo de enlaces para resetear.")

# Ignorar mensajes no válidos
@bot.on(events.NewMessage)
async def ignore_invalid_commands(event):
    # No responder a mensajes que no coincidan con los comandos registrados
    pass

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text.startswith('/'):
        return

    # Verifica si el usuario está autorizado antes de procesar la URL
    if event.sender_id not in AUTHORIZED_USERS:
        logging.warning(f"Intento de guardar enlace no autorizado por el usuario: {event.sender_id}")
        await event.respond("❗ No tienes permiso para guardar enlaces.")
        return

    # Ignorar los enlaces m3u8 para la grabación general
    if event.text.endswith('.m3u8'):
        logging.info("Ignorando enlace m3u8 para la grabación general.")
        return

    # Verifica si el usuario tiene un clip pendiente y no guarda el enlace si es así
    if event.sender_id in pending_clips and pending_clips[event.sender_id]:
        logging.info(f"Ignorando el enlace porque es un clip pendiente para el usuario {event.sender_id}")
        return
    
    # Procesar el enlace si es válido y no está en proceso
    if event.text and is_valid_url(event.text):
        url = event.text
        
        # Verifica si el enlace ya está en proceso de descarga
        if url in active_downloads:
            await event.respond("⚠️ Este enlace ya está en proceso de descarga.")
            return

        # Guardar el enlace y notificar al usuario
        add_link(str(event.sender_id), url)
        await event.respond(f"🌐 URL guardada: {url}")
        await event.respond(
            "⚠️ <b>¡Inicio de Monitoreo cada minuto...!</b>\n\n",
            parse_mode='html'
        )

        # Añadir el enlace a descargas activas y crear una nueva tarea
        active_downloads.add(url)
        asyncio.create_task(handle_link(event.chat_id, event.sender_id, url))

async def handle_link(chat_id, user_id, link):
    global driver  # Reutilizar el driver global
    if driver is None:
        driver = setup_driver()  # Configura el driver solo si aún no está inicializado

    try:
        # Llama a la función de verificación y descarga
        await verify_and_download(link, user_id, chat_id, driver)
    except Exception as e:
        logging.error(f"Error en handle_link para {link}: {e}")
    # No cerramos el driver aquí para reutilizarlo en otras llamadas

async def verify_and_download(link, user_id, chat_id, driver):
    # Verifica y descarga usando el driver
    m3u8_link = await extract_last_m3u8_link(driver, link)
    if m3u8_link:
        await download_with_yt_dlp(m3u8_link, user_id, "modelo_nombre", link, chat_id)
    else:
        await bot.send_message(chat_id, "❌ No se pudo obtener un enlace de transmisión válido.")

# Bienvenida
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    mensaje = (
        "👋 <b>¡Bienvenido al Bot de Grabación Automática!</b>\n\n"
        "Este bot puede ayudarte a grabar y gestionar transmisiones en directo de forma automática.\n\n"
        "<b>Comandos disponibles:</b>\n\n"
        "• <b>/grabar</b> - Inicia el monitoreo y grabación automática de una transmisión en vivo.\n"
        "• <b>/check_modelo</b> - Muestra una lista de modelos actualmente en grabación. Selecciona un modelo para ver detalles.\n"
        "• <b>/check_grabaciones</b> - Lista las grabaciones activas, permitiendo detenerlas y procesarlas para subirlas.\n\n"
        "• <b>/mis_enlaces</b> - Muestra los enlaces de transmisiones guardados por el usuario.\n"
        "• <b>/eliminar_enlace</b> - Elimina un enlace guardado (usa: <code>/eliminar_enlace [enlace]</code>).\n"
        "• <b>/status</b> - Verifica el estado general del bot.\n\n"
        "Para comenzar, puedes enviar el comando <code>/grabar</code> seguido de la URL de la transmisión. ¡Disfruta!\n"
    )
    
    await event.respond(mensaje, parse_mode='html')

if __name__ == '__main__':
    logging.info("Iniciando el bot de Telegram")
    
    # Lanza la verificación de enlaces en paralelo
    bot.loop.create_task(verificar_enlaces())
    bot.run_until_disconnected()
