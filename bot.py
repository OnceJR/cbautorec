from telethon import TelegramClient, events, Button
import asyncio
import subprocess
import re
import os

# Reemplaza con tus credenciales de API de Telegram
api_id = '24738183'
api_hash = '6a1c48cfe81b1fc932a02c4cc1d312bf'
bot_token = '8031762443:AAHCCahQLQvMZiHx4YNoVzuprzN3s_BM8Es'

bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# Configuración de ffmpeg para calidad Alta y Media
ffmpeg_config = {
    'alta': '-c:v libx264 -crf 20 -preset veryfast -c:a aac -b:a 128k',
    'media': '-c:v libx264 -crf 28 -preset superfast -c:a aac -b:a 96k'
}

# Variables globales
grabando = False
proceso_ffmpeg = None
archivo_salida = None
chat_id = None
mensaje_id = None

async def grabar_video(url, calidad, duracion=None):
  global proceso_ffmpeg, archivo_salida
  archivo_salida = f"video_{chat_id}_{mensaje_id}.mp4"
  comando_ffmpeg = [
      'ffmpeg',
      '-i', url,
      '-c copy', # Copiar códecs de la transmisión para mejor compatibilidad
      ffmpeg_config[calidad]
  ]
  if duracion:
    comando_ffmpeg.extend(['-t', str(duracion)])
  comando_ffmpeg.append(archivo_salida)
  
  proceso_ffmpeg = await asyncio.create_subprocess_exec(
      *comando_ffmpeg,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE
  )
  
  await proceso_ffmpeg.wait()

async def dividir_archivo(nombre_archivo):
  """Divide un archivo en partes de 2GB."""
  partes = []
  tamaño_parte = 2 * 1024 * 1024 * 1024  # 2GB en bytes

  with open(nombre_archivo, 'rb') as f:
    while True:
      parte = f.read(tamaño_parte)
      if not parte:
        break
      nombre_parte = f"{nombre_archivo}.part{len(partes) + 1}"
      with open(nombre_parte, 'wb') as f_parte:
        f_parte.write(parte)
      partes.append(nombre_parte)

  return partes

async def subir_archivo(chat_id, nombre_archivo):
  """Sube un archivo o sus partes si es mayor a 2GB."""
  tamaño_archivo = os.path.getsize(nombre_archivo)
  if tamaño_archivo > 2 * 1024 * 1024 * 1024:
    partes = await dividir_archivo(nombre_archivo)
    for parte in partes:
      await bot.send_file(chat_id, parte, supports_streaming=True)
      os.remove(parte)
  else:
    await bot.send_file(chat_id, nombre_archivo, supports_streaming=True)
  os.remove(nombre_archivo)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
  await event.respond("""
  Bienvenido! Soy un bot para grabar transmisiones en vivo. 
  
  **Comandos:**
  
  /grabar_clip: Graba un clip de 30 segundos.
  /grabar_completo: Graba la transmisión completa.
  /detener: Detiene la grabación y sube el video.
  
  **Para usarme, envía un enlace de transmisión válido (http o https).**
  """)

@bot.on(events.NewMessage(pattern='(http|https)://.*'))
async def procesar_enlace(event):
  global grabando, chat_id, mensaje_id
  if not grabando:
    chat_id = event.chat_id
    mensaje_id = event.id
    url = event.text
    await event.respond(
        "Selecciona una opción:",
        buttons=[
            [Button.inline("Clip (30s) - Alta calidad", data=b"clip_alta")],
            [Button.inline("Clip (30s) - Media calidad", data=b"clip_media")],
            [Button.inline("Completo - Alta calidad", data=b"completo_alta")],
            [Button.inline("Completo - Media calidad", data=b"completo_media")]
        ]
    )

@bot.on(events.CallbackQuery)
async def manejar_callback(event):
  global grabando
  await event.answer()
  opcion = event.data.decode()
  if opcion.startswith('clip'):
    grabando = True
    calidad = opcion.split('_')[1]
    await event.edit("Grabando clip de 30 segundos...")
    await grabar_video(event.message.reply_to_msg_id.text, calidad, 30)
    await event.edit("Subiendo clip...")
    await subir_archivo(event.chat_id, archivo_salida)
    await event.edit("¡Clip subido!")
    grabando = False
  elif opcion.startswith('completo'):
    grabando = True
    calidad = opcion.split('_')[1]
    await event.edit("Grabando transmisión completa...")
    await grabar_video(event.message.reply_to_msg_id.text, calidad)
    await event.edit("Subiendo video...")
    await subir_archivo(event.chat_id, archivo_salida)
    await event.edit("¡Video subido!")
    grabando = False

@bot.on(events.NewMessage(pattern='/detener'))
async def detener_grabacion(event):
  global grabando, proceso_ffmpeg
  if grabando:
    grabando = False
    if proceso_ffmpeg:
      try:
        proceso_ffmpeg.kill()
        await event.respond("Grabación detenida. Subiendo video...")
        await subir_archivo(event.chat_id, archivo_salida)
        await event.respond("¡Video subido!")
      except ProcessLookupError:
        await event.respond("No hay ninguna grabación en curso.")
  else:
    await event.respond("No hay ninguna grabación en curso.")

bot.run_until_disconnected()
