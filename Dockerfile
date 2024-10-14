# Usar una imagen base de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar los archivos de requisitos e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar FFmpeg y codecs adicionales
RUN apt-get update && apt-get install -y ffmpeg libavcodec-extra && rm -rf /var/lib/apt/lists/*

# Copiar el resto de tu aplicación
COPY . .

# Comando para ejecutar tu aplicación
CMD ["python", "bot.py"]
