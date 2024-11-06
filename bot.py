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

# Configuración de la API
API_ID = 24738183
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'
BOT_TOKEN = "7882998171:AAGF6p9RYqMlKuEw8Ssyk2ZTsBcD59Ree-c"

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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

async def upload_and_delete_mp4_files(user_id, chat_id):
    try:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        tasks = []  # Lista de tareas para procesar los archivos en paralelo

        for file in files:
            tasks.append(asyncio.create_task(handle_file_upload(user_id, chat_id, file)))

        # Esperar a que todas las tareas terminen sin bloquear el bot
        await asyncio.gather(*tasks)

    except Exception as e:
        logging.error(f"Error en la función upload_and_delete_mp4_files: {e}")
        await bot.send_message(user_id, f"❌ Error en el proceso de subida y eliminación: {e}")

async def handle_file_upload(user_id, chat_id, file):
    file_path = os.path.join(DOWNLOAD_PATH, file)
    command = ["rclone", "copy", file_path, GDRIVE_PATH]
    
    try:
        # Ejecutar el proceso de subida a Google Drive
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
            else:
                logging.error(f"Error al crear enlace compartido para {file}: {share_stderr.decode('utf-8')}")
                await bot.send_message(user_id, f"❌ Error al crear enlace compartido para: {file}")
        else:
            logging.error(f"Error al subir {file}: {stderr.decode('utf-8')}")
            await bot.send_message(user_id, f"❌ Error al subir el archivo: {file}")
            return

        # Obtener duración y dimensiones del video usando ffmpeg
        duration, width, height = await get_video_metadata(file_path)
        if duration is None or width is None or height is None:
            await bot.send_message(user_id, f"❌ Error al obtener metadatos del archivo: {file}")
            return

        # Generar una miniatura temporal única
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_thumb:
            thumbnail_path = temp_thumb.name
        thumbnail_command = [
            "ffmpeg", "-i", file_path, "-ss", "00:00:01.000", "-vframes", "1", thumbnail_path
        ]
        subprocess.run(thumbnail_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Envío del video al chat de Telegram con soporte para streaming y miniatura
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
        
        # Eliminar el archivo de miniatura y el archivo de video local tras envío exitoso
        os.remove(thumbnail_path)
        os.remove(file_path)
        logging.info(f"Archivo eliminado: {file}")

    except Exception as e:
        logging.error(f"Error en la función handle_file_upload para {file}: {e}")
        await bot.send_message(user_id, f"❌ Error en el proceso de subida y eliminación para {file}: {e}")

async def send_large_file(chat_id, file_path, bot):
    # Obtener duración del video con FFmpeg
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    total_duration = float(result.stdout)  # Duración total en segundos
    part_duration = 60 * 30  # 30 minutos por parte

    current_time = 0
    part_num = 1

    while current_time < total_duration:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            part_path = temp_file.name

        # Dividir video en partes usando FFmpeg
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path, "-ss", str(current_time), "-t", str(part_duration),
            "-c", "copy", part_path
        ])
        
        # Enviar el archivo de video por partes
        await bot.send_file(chat_id, part_path, caption=f"📹 Parte {part_num}")

        # Eliminar parte temporal después de enviarla
        os.remove(part_path)

        # Actualizar tiempos para la siguiente parte
        current_time += part_duration
        part_num += 1

async def download_with_yt_dlp(m3u8_url, user_id, modelo, original_link, chat_id):
    # Formatear la fecha y hora actual
    fecha_hora = time.strftime("%Y%m%d_%H%M%S")
    output_file_path = os.path.join(DOWNLOAD_PATH, f"{modelo}_{fecha_hora}.mp4")
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', output_file_path]
    
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url} para {modelo}")
        # Enviar el mensaje al chat original (grupo o privado)
        await bot.send_message(chat_id, f"🔴 Iniciando grabación: {original_link}")

        # Agregar a grabaciones
        grabaciones[modelo] = {
            'inicio': time.time(),
            'file_path': output_file_path,
            'user_id': user_id,
        }

        # Ejecutar la descarga en segundo plano
        process = await asyncio.create_subprocess_exec(
            *command_yt_dlp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL  # Ignorar los mensajes de error y advertencia
        )
        
        # Leer la salida de stdout para monitorear el progreso de la descarga
        async def read_output(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break
                # Extraer y mostrar el tamaño de la descarga si está disponible en la salida
                decoded_line = line.decode().strip()
                if "M" in decoded_line:  # Puedes ajustar esto según el formato de salida
                    logging.info(f"Progreso de descarga: {decoded_line}")

        # Leer stdout en tiempo real para mostrar el tamaño
        await read_output(process.stdout)

        # Esperar a que el proceso termine
        await process.wait()

        if process.returncode == 0:
            # Obtener el tamaño del archivo descargado
            file_size = os.path.getsize(output_file_path) / (1024 ** 2)  # Tamaño en MB
            logging.info(f"Descarga completa para {modelo}. Tamaño del archivo: {file_size:.2f} MB")
            await bot.send_message(chat_id, f"✅ Grabación completa para {modelo}. Tamaño del archivo: {file_size:.2f} MB")
            await upload_and_delete_mp4_files(user_id, chat_id)
        else:
            await bot.send_message(chat_id, f"❌ Error al descargar para {modelo}: Código de error {process.returncode}")

    except Exception as e:
        logging.error(f"Error durante la descarga para {modelo}: {e}")
        await bot.send_message(chat_id, f"❌ Error durante la descarga para {modelo}: {e}")
    finally:
        # Elimina la grabación del diccionario, independientemente del resultado
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

# Función para enviar el mensaje con el botón inline
@bot.on(events.NewMessage(pattern='/check_modelo'))
async def check_modelo(event):
    if len(event.raw_text.split()) < 2:
        await event.respond("Por favor, proporciona el nombre de la modelo después del comando.")
        return

    nombre_modelo = event.raw_text.split()[1]
    
    # Crear el botón inline para mostrar el estado de la modelo
    buttons = [
        [Button.inline(f"Estado de {nombre_modelo}", data=f"alerta_modelo:{nombre_modelo}")]
    ]
    await event.respond("Haz clic en el botón para ver el estado de la modelo:", buttons=buttons)

# Función que recibe el callback del botón y simula una alerta
@bot.on(events.CallbackQuery(data=lambda data: data.startswith(b"alerta_modelo")))
async def callback_alert(event):
    # Extrae el nombre de la modelo desde el callback data
    modelo_url = event.data.decode().split(':')[1]
    modelo = modelo_url.split('/')[-1]  # Extrae el nombre de la modelo al final del enlace

    # Obtener el estado actual de la modelo
    mensaje_alerta, online = await obtener_informacion_modelo(modelo, event.sender_id)

    # Enviar el mensaje como una alerta emergente
    await event.answer(mensaje_alerta, alert=True)
    
# Verificación y extracción periódica de enlaces m3u8 modificada para incluir el enlace original
async def verificar_enlaces():
    while True:
        driver = setup_driver()  # Inicializar un nuevo driver en cada ciclo para evitar problemas de memoria
        links = load_links()
        if not links:
            logging.warning("No se cargaron enlaces guardados.")
            await asyncio.sleep(60)
            continue

        tasks = []  # Lista de tareas para procesar los enlaces en paralelo
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
                    task = asyncio.create_task(process_link(driver, user_id, link))
                    tasks.append(task)
                    processed_links[link] = task

        if tasks:
            await asyncio.gather(*tasks)

        logging.info("Verificación de enlaces completada. Esperando 60 segundos para la próxima verificación.")
        driver.quit()  # Cerrar el driver en cada ciclo para liberar recursos
        await asyncio.sleep(60)

async def process_link(driver, user_id, link):
    m3u8_link = await extract_last_m3u8_link(driver, link)
    if m3u8_link:
        modelo = link.rstrip('/').split('/')[-1]

        # Verificar si ya hay una grabación activa
        if modelo in grabaciones and grabaciones[modelo].get('grabando'):
            await alerta_emergente(modelo, 'online', user_id)
        else:
            # Iniciar una nueva grabación en paralelo
            await download_with_yt_dlp(m3u8_link, user_id, modelo, link, user_id)
    else:
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

# Variable temporal para almacenar el estado del enlace en espera de cada usuario
pending_clips = {}

@bot.on(events.NewMessage(pattern='/clip'))
async def start_clip(event):
    # Verifica si el usuario está autorizado
    if event.sender_id not in AUTHORIZED_USERS:
        await event.reply("❌ No tienes permiso para usar este comando.")
        return

    # Solicita el enlace al usuario y guarda su estado como "pendiente"
    await event.reply("📥 Por favor, envíame el enlace del stream para grabar un clip de 30 segundos.")
    pending_clips[event.sender_id] = True

@bot.on(events.NewMessage)
async def process_clip_link(event):
    # Verifica si el usuario tiene un clip pendiente y si ha enviado un enlace válido
    if event.sender_id in pending_clips and pending_clips[event.sender_id]:
        url = event.text

        # Verifica si es un enlace válido (usando is_valid_url o similar)
        if not is_valid_url(url):
            await event.reply("❌ Por favor, envía un enlace válido.")
            return
        
        # Configura los parámetros de grabación
        model_name = url.split('/')[-1].split('.')[0]  # Extrae el nombre del modelo de la URL
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{DOWNLOAD_PATH}{model_name}_{timestamp}_clip.mp4"
        
        await event.reply("🎥 Iniciando la grabación del clip de 30 segundos...")

        # Comando para grabar 30 segundos del stream usando ffmpeg
        record_command = [
            "ffmpeg", "-y", "-i", url, "-t", "30", 
            "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", 
            "-c:a", "aac", "-b:a", "128k", filename
        ]
        
        try:
            # Ejecuta el comando de grabación de forma asincrónica
            process = await asyncio.create_subprocess_exec(
                *record_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                await event.reply("❌ Error durante la grabación del clip.")
                logging.error(stderr.decode())  # Registrar el error en los logs
                return
        except Exception as e:
            await event.reply(f"❌ Ocurrió un error: {str(e)}")
            logging.error(f"Error: {e}")
            return

        # Enviar el clip al usuario
        await event.reply("✅ Grabación completada. Enviando el clip...")
        await bot.send_file(event.chat_id, filename, caption="🎬 Aquí tienes tu clip grabado de 30 segundos.")
        
        # Elimina el archivo local después de enviar
        os.remove(filename)

        # Elimina el estado pendiente para este usuario
        del pending_clips[event.sender_id]

# Comando para resetear enlaces
@bot.on(events.NewMessage(pattern='/reset_links'))
async def reset_links(event):
    user_id = str(event.sender_id)
    if user_id == "1170684259":  # Solo el admin puede usar este comando
        os.remove(LINKS_FILE)
        await event.respond("✅ Enlaces reseteados exitosamente.")
    else:
        await event.respond("❗ No tienes permiso para usar este comando.")

# Ignorar mensajes no válidos
@bot.on(events.NewMessage)
async def ignore_invalid_commands(event):
    # No responder a mensajes que no coincidan con los comandos registrados
    pass

active_downloads = set()  # Conjunto para rastrear descargas activas

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text.startswith('/'):
        return

    # Verifica si el usuario está autorizado antes de procesar la URL
    if event.sender_id not in AUTHORIZED_USERS:
        logging.warning(f"Intento de guardar enlace no autorizado por el usuario: {event.sender_id}")
        await event.respond("❗ No tienes permiso para guardar enlaces.")
        return
    
    # Procesar el enlace si es válido y no está en proceso
    if event.text and is_valid_url(event.text):
        url = event.text
        if url in active_downloads:
            await event.respond("⚠️ Este enlace ya está en proceso de descarga.")
            return

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
    try:
        # Lógica de verificación y descarga (llama a funciones que manejen la descarga y verificación)
        await verify_and_download(link, user_id, chat_id)
    finally:
        # Remover el enlace de descargas activas cuando termine
        active_downloads.remove(link)

async def verify_and_download(link, user_id, chat_id):
    # Implementa la lógica de verificación del enlace y descarga
    m3u8_link = await extract_last_m3u8_link(driver, link)  # Verificación de enlace
    if m3u8_link:
        # Iniciar la descarga en una tarea independiente
        await download_with_yt_dlp(m3u8_link, user_id, "modelo_nombre", link, chat_id)
    else:
        await bot.send_message(chat_id, "❌ No se pudo obtener un enlace de transmisión válido.")

# Bienvenida
@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.respond(
        "👋 <b>¡Bot de Grabación Automatica!</b>\n\n"
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
    
    bot.loop.create_task(verificar_enlaces())  # Lanza la verificación en paralelo
    bot.run_until_disconnected()
