import subprocess
import time
import os
import logging
import glob
import requests
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
def extract_last_m3u8_link(driver, chaturbate_link):
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

# Uso del código para extraer enlace m3u8
if __name__ == "__main__":
    chaturbate_link = "https://chaturbate.com/example"  # Enlace de ejemplo de Chaturbate
    driver = setup_driver()
    m3u8_link = extract_last_m3u8_link(driver, chaturbate_link)
    if m3u8_link:
        print(f"Enlace m3u8 encontrado: {m3u8_link}")
    else:
        print("No se encontró enlace m3u8.")
    driver.quit()

# Subir y eliminar archivos mp4
async def upload_and_delete_mp4_files(user_id):
    try:
        files = [f for f in os.listdir(DOWNLOAD_PATH) if f.endswith('.mp4')]
        
        for file in files:
            file_path = os.path.join(DOWNLOAD_PATH, file)
            command = ["rclone", "copy", file_path, GDRIVE_PATH]
            
            # Cambiamos subprocess.run por asyncio.create_subprocess_exec
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
                    await bot.send_message(int(user_id), f"✅ Video subido: {file}\n🔗 Enlace: {shared_link}")
                else:
                    logging.error(f"Error al crear enlace compartido para {file}: {share_stderr.decode('utf-8')}")
                    await bot.send_message(int(user_id), f"❌ Error al crear enlace compartido para: {file}")
            else:
                logging.error(f"Error al subir {file}: {stderr.decode('utf-8')}")
                await bot.send_message(int(user_id), f"❌ Error al subir el archivo: {file}")  # Notificar al usuario
                continue  # Saltar la eliminación del archivo si la subida falló
            
            # Solo eliminar el archivo si la subida fue exitosa
            try:
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file}")
            except Exception as e:
                logging.error(f"Error al eliminar el archivo {file}: {e}")
                await bot.send_message(int(user_id), f"❌ Error al eliminar el archivo: {file}")

    except Exception as e:
        logging.error(f"Error en la función upload_and_delete_mp4_files: {e}")
        await bot.send_message(int(user_id), f"❌ Error en el proceso de subida y eliminación: {e}")

# Descargar con yt-dlp (asíncrono) con título modificado
async def download_with_yt_dlp(m3u8_url, user_id, modelo, original_link):
    # Formatear la fecha y hora actual
    fecha_hora = time.strftime("%Y%m%d_%H%M%S")
    output_file_path = os.path.join(DOWNLOAD_PATH, f"{modelo}_{fecha_hora}.mp4")
    command_yt_dlp = ['yt-dlp', '-f', 'best', m3u8_url, '-o', output_file_path]
    try:
        logging.info(f"Iniciando descarga con yt-dlp: {m3u8_url} para {modelo}")
        await bot.send_message(int(user_id), f"🔴 Iniciando grabación: {original_link}")

        # Agregar a grabaciones
        grabaciones[modelo] = {
        'inicio': time.time(),
        'file_path': output_file_path,
        'user_id': user_id,
    }

        process = await asyncio.create_subprocess_exec(
            *command_yt_dlp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logging.info(f"Descarga completa para {modelo}.")
            await bot.send_message(int(user_id), f"✅ Grabación completa para {modelo}.")
            await upload_and_delete_mp4_files(user_id)
        else:
            stderr = stderr.decode('utf-8')
            logging.error(f"Error al descargar para {modelo}: {stderr}")
            await bot.send_message(int(user_id), f"❌ Error al descargar para {modelo}: {stderr}")
    except Exception as e:
        logging.error(f"Error durante la descarga para {modelo}: {e}")
        await bot.send_message(int(user_id), f"❌ Error durante la descarga para {modelo}: {e}")
    finally:
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
                    m3u8_link = await extract_last_m3u8_link(link)  # Asegúrate de que esta función sea asíncrona
                    if m3u8_link:
                        modelo = link.rstrip('/').split('/')[-1]
                        
                        # Si hay una grabación activa, informa al usuario pero no inicia una nueva grabación
                        if modelo in grabaciones and grabaciones[modelo]['grabando']:
                            await alerta_emergente(modelo, 'online', user_id)
                            continue  # No iniciar una nueva grabación

                        # Si no hay grabación activa, inicia la grabación
                        task = asyncio.create_task(download_with_yt_dlp(m3u8_link, user_id, modelo, link))
                        tasks.append(task)
                        processed_links[link] = task
                    else:
                        modelo = link.rstrip('/').split('/')[-1]
                        if modelo in grabaciones:
                            await alerta_emergente(modelo, 'offline', user_id)
                            grabaciones.pop(modelo, None)
                        logging.warning(f"No se pudo obtener un enlace m3u8 válido para el enlace: {link}")

        if tasks:
            await asyncio.gather(*tasks)

        logging.info("Verificación de enlaces completada. Esperando 60 segundos para la próxima verificación.")
        await asyncio.sleep(60)

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
    
    # Ignorar comandos que comienzan con '/' pero no son el comando actual
    if event.text.startswith('/') and event.text.split()[0] not in ['/grabar', '/start', '/mis_enlaces', '/eliminar_enlace', '/status']:
        return
    
    # Procesar solo si el usuario está autorizado
    if event.sender_id in AUTHORIZED_USERS:
        if is_valid_url(event.text):
            add_link(event.sender_id, event.text)
            await event.respond("✅ Enlace guardado para grabación.")
        else:
            # No respondas nada si la URL es inválida
            return
    else:
        logging.warning(f"Intento de guardar enlace no autorizado por el usuario: {event.sender_id}")
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

# Ignorar mensajes no válidos
@bot.on(events.NewMessage)
async def ignore_invalid_commands(event):
    # No responder a mensajes que no coincidan con los comandos registrados
    pass

@bot.on(events.NewMessage)
async def process_url(event):
    if event.text.startswith('/'):
        return
    
    if event.text and is_valid_url(event.text):  # Eliminar await aquí
        add_link(str(event.sender_id), event.text)
        await event.respond(f"🌐 URL guardada: {event.text}")
        await event.respond(
            "⚠️ <b>¡inicio de Monitoreo cada minuto...!</b>\n\n",
            parse_mode='html'
        )
    # Si la URL no es válida, no hacemos nada y simplemente ignoramos el mensaje.

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
