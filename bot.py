import subprocess
import time
import os
import logging
from telethon import TelegramClient, events
from selenium import webdriver
from selenium.webdriver.common.by import By
import asyncio

# Configuración de la API de Telegram
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('my_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Configurar logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el navegador
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")  # Descomentar si no deseas abrir la ventana del navegador
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# Almacena el último modelo procesado y estado de descarga
last_model = None
downloading = False

# Función para extraer enlaces m3u8
def extract_m3u8_links(chaturbate_link):
    driver.get("https://onlinetool.app/ext/m3u8_extractor")
    time.sleep(3)
    
    input_field = driver.find_element(By.NAME, "url")
    input_field.clear()  # Limpia el campo antes de insertar
    input_field.send_keys(chaturbate_link)
    
    run_button = driver.find_element(By.XPATH, '//button[span[text()="Run"]]')
    run_button.click()
    
    time.sleep(5)
    m3u8_links = driver.find_elements(By.XPATH, '//pre/a')
    return [link.get_attribute('href') for link in m3u8_links]

def download_best_quality(m3u8_links, chat_id):
    global downloading
    if m3u8_links:
        # Selecciona el último enlace como el de mejor calidad
        best_quality_link = m3u8_links[-1]  # El último enlace
        logging.info(f"Descargando la mejor calidad: {best_quality_link}")
        downloading = True
        
        # Ejecutar el comando de descarga
        result = subprocess.run(['yt-dlp', best_quality_link], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode == 0:
            downloaded_file = "video_descargado.mp4"
            logging.info(f"Descarga completa. Enviando archivo al chat...")
            asyncio.run(send_file_to_chat(chat_id, downloaded_file))
        else:
            logging.error(f"Error durante la descarga: {result.stderr.decode()}")
            asyncio.run(bot.send_message(chat_id, "No se pudo descargar el video."))
        
        downloading = False
    else:
        logging.info("No se encontraron enlaces .m3u8.")

async def send_file_to_chat(chat_id, file_path):
    await bot.send_file(chat_id, file_path)  # Envía el archivo al chat
    os.remove(file_path)  # Elimina el archivo después de enviarlo
    logging.info(f"Archivo {file_path} enviado y eliminado.")

def main():
    global last_model, downloading
    
    while True:
        chaturbate_link = input("Ingresa el enlace de Chaturbate: ")
        
        # Verifica si el modelo ha cambiado o si no hay descarga en curso
        if chaturbate_link != last_model and not downloading:
            last_model = chaturbate_link
            logging.info(f"Verificando enlaces para: {chaturbate_link}")

            m3u8_links = extract_m3u8_links(chaturbate_link)
            
            # Descarga si hay nuevos enlaces
            download_best_quality(m3u8_links, "YOUR_CHAT_ID")  # Reemplaza con el ID de tu chat

        else:
            logging.info("Descarga en curso o el modelo no ha cambiado.")

        logging.info("Esperando un minuto para la próxima verificación...")
        time.sleep(60)  # Espera 1 minuto

# Ejecuta el programa
try:
    main()
finally:
    driver.quit()
