import subprocess
import time
import os
from telethon import TelegramClient, events, Button
import asyncio

# Configuración de la API
API_ID = 24738183  # Reemplaza con tu App API ID
API_HASH = '6a1c48cfe81b1fc932a02c4cc1d312bf'  # Reemplaza con tu App API Hash
BOT_TOKEN = "8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es"  # Reemplaza con tu Bot Token

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Diccionario para almacenar datos de los usuarios y enlaces de monitoreo
user_links = {}

# Función para dividir archivos en partes de 2 GB
def dividir_archivo(file_path, max_size=2 * 1024 * 1024 * 1024):  # 2 GB
    file_parts = []
    file_size = os.path.getsize(file_path)
    part_num = 1

    with open(file_path, 'rb') as f:
        while f.tell() < file_size:
            part_path = f"{file_path}_part{part_num}.mp4"
            with open(part_path, 'wb') as part_file:
                part_file.write(f.read(max_size))
            file_parts.append(part_path)
            part_num += 1

    return file_parts

# Función que realiza la grabación o extracción del clip
async def extraer_clip(link):
    # Simular proceso de extracción de clip de un minuto desde el enlace
    print(f"Extrayendo clip de un minuto desde {link}...")
    await asyncio.sleep(60)  # Simular duración de un minuto
    print(f"Clip extraído desde {link}.")

# Función que programa la extracción automática de clips cada minuto
async def programar_extraccion_automatica(link):
    while True:
        await extraer_clip(link)
        await asyncio.sleep(60)  # Espera un minuto antes de extraer el siguiente clip

# Evento para manejar la respuesta del usuario cuando ingresa el enlace
@bot.on(events.NewMessage(pattern='/setlink'))
async def set_link(event):
    # Solicitar al usuario que ingrese el enlace
    sender = await event.get_sender()
    user_id = sender.id
    await event.respond("Por favor, envía el enlace a monitorear.")

    # Esperar la respuesta del usuario con el enlace
    response = await bot.wait_for(events.NewMessage(from_user=user_id))
    link = response.text

    # Almacenar el enlace en el diccionario del usuario
    user_links[user_id] = link
    await event.respond(f"¡Enlace configurado! Comenzando a monitorear: {link}")

    # Iniciar el monitoreo automático del enlace
    await programar_extraccion_automatica(link)

# Evento que se ejecuta cuando el bot arranca con un botón para iniciar la configuración
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    # Mostrar un botón para que el usuario configure el enlace
    await event.respond(
        "¡Bienvenido! Haz clic en el botón para configurar el enlace a monitorear.",
        buttons=[Button.text("Configurar enlace", resize=True, single_use=True)]
    )

# Evento para manejar cuando el usuario hace clic en el botón para configurar el enlace
@bot.on(events.CallbackQuery)
async def callback_query_handler(event):
    if event.data == b"Configurar enlace":
        await event.respond("/setlink")  # Ejecutar el comando para configurar el enlace

# Iniciar el bot
print("Bot iniciado...")
bot.run_until_disconnected()
