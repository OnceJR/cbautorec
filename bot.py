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
calidad = 'media'  # Calidad por defecto


async def grabar_video(evento, url, duracion=None):
  global grabando, proceso_ffmpeg, archivo_salida, calidad

  if grabando:
    await evento.respond("Ya se está grabando un video.")
    return

  grabando = True
  archivo_salida = f"video_{evento.chat_id}.mp4"

  comando_ffmpeg = [
      'ffmpeg',
      '-i', url,
      '-c copy',  # Copiar códecs de la transmisión original si es posible
      ffmpeg_config[calidad]
  ]

  if duracion:
    comando_ffmpeg.extend(['-t', str(duracion)])

  try:
    # Crear el proceso ffmpeg de forma asíncrona
    proceso_ffmpeg = await asyncio.create_subprocess_exec(
        *comando_ffmpeg,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    await evento.respond("Grabando video...")

    # Esperar a que el proceso termine con un timeout
    stdout, stderr = await asyncio.wait_for(proceso_ffmpeg.communicate(), timeout=3600)

    if proceso_ffmpeg.returncode != 0:
      await evento.respond(f"Error al grabar el video: {stderr.decode()}")
  except asyncio.TimeoutError:
    if proceso_ffmpeg:
      proceso_ffmpeg.terminate()
    await evento.respond("Error: Tiempo de grabación excedido.")
  finally:
    grabando = False


async def dividir_archivo(nombre_archivo):
  """Divide un archivo grande en partes de 2GB."""
  tamano_parte = 2 * 1024 * 1024 * 1024  # 2GB en bytes
  with open(nombre_archivo, 'rb') as f:
    indice_parte = 1
    while True:
      parte = f.read(tamano_parte)
      if not parte:
        break
      nombre_parte = f"{nombre_archivo}.part{indice_parte}"
      with open(nombre_parte, 'wb') as f_parte:
        f_parte.write(parte)
      indice_parte += 1
  os.remove(nombre_archivo)  # Eliminar el archivo original


async def subir_video(evento):
  global archivo_salida
  if not archivo_salida or not os.path.exists(archivo_salida):
    await evento.respond("No hay ningún video grabado.")
    return

  try:
    tamano_archivo = os.path.getsize(archivo_salida)
    if tamano_archivo > 2 * 1024 * 1024 * 1024:  # 2GB en bytes
      await evento.respond("El video es demasiado grande. Dividiendo en partes...")
      await dividir_archivo(archivo_salida)
      await evento.respond("Subiendo partes del video...")
      for filename in os.listdir():
        if filename.startswith(archivo_salida + ".part"):
          await bot.send_file(evento.chat_id, filename, supports_streaming=True)
          os.remove(filename)
    else:
      await evento.respond("Subiendo video...")
      await bot.send_file(evento.chat_id, archivo_salida, supports_streaming=True)
    os.remove(archivo_salida)
    archivo_salida = None
  except Exception as e:
    await evento.respond(f"Error al subir el video: {e}")


@bot.on(events.NewMessage(pattern='/start'))
async def start(evento):
  await evento.respond(
      "¡Hola! Soy un bot para grabar transmisiones en vivo. "
      "Por favor, elige la calidad de grabación y envía el enlace de la transmisión.",
      buttons=[
          [Button.inline("Alta", data=b'alta')],
          [Button.inline("Media", data=b'media')]
      ]
  )


@bot.on(events.CallbackQuery)
async def manejar_calidad(evento):
  global calidad
  calidad = evento.data.decode('utf-8')
  await evento.answer("Calidad seleccionada.")
  await evento.edit("Ahora envía el enlace de la transmisión (opcionalmente seguido de la duración en segundos para grabar un clip).")


@bot.on(events.NewMessage)
async def manejar_enlace(evento):
  global calidad
  mensaje = evento.message.text
  # Expresión regular para validar enlaces HTTP/HTTPS con duración opcional
  match = re.match(r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*) ?(\d+)?', mensaje)
  if match:
    url, duracion = match.groups()
    duracion = int(duracion) if duracion else None
    await grabar_video(evento, url, duracion=duracion)
  elif not evento.message.text.startswith('/'):
    await evento.respond("Por favor, envía un enlace válido (opcionalmente seguido de la duración en segundos para grabar un clip).")


@bot.on(events.NewMessage(pattern='/detener'))
async def detener_grabacion(evento):
  global proceso_ffmpeg, grabando
  if not grabando:
    await evento.respond("No se está grabando ningún video.")
    return

  if proceso_ffmpeg:
    proceso_ffmpeg.terminate()
  grabando = False
  await subir_video(evento)


bot.run_until_disconnected()
