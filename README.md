
# 📡 **CB Auto Recorder Bot**

🚀 **CB Auto Recorder Bot** es un bot de Telegram diseñado para grabar automáticamente transmisiones en vivo y clips, procesarlos y subirlos a Google Drive y Telegram. Ideal para usuarios que buscan automatizar la gestión de grabaciones de modelos y transmisiones en directo.

---

## 📋 **Características**

- 🟢 **Monitoreo Automático**: Detecta y graba transmisiones en vivo desde enlaces proporcionados.
- 🎬 **Grabación de Clips**: Crea clips de 30 segundos para momentos destacados.
- 📂 **Gestión de Archivos**: Procesa videos (división, miniaturas) y los sube a Google Drive y Telegram.
- 📊 **Progreso en Tiempo Real**: Rastrea el estado de las descargas y subidas.
- 🛠️ **Interfaz con Botones**: Permite detener grabaciones activas y gestionar grabaciones desde el bot.
- 🔐 **Autorización Segura**: Acceso limitado a usuarios autorizados.

---

## 🛠️ **Requisitos del Sistema**

1. **Sistema Operativo**: Linux recomendado (probado en Ubuntu/Debian).
2. **Python**: Versión 3.10 o superior.
3. **Dependencias**:
   - `Telethon`
   - `aiohttp`
   - `selenium`
   - `yt-dlp`
   - `ffmpeg`
   - `rclone`

4. **Google Chrome y Chromedriver**: Para manejar extracción de enlaces m3u8.

---

## ⚙️ **Instalación**

1. **Clona el repositorio**:
   ```bash
   git clone https://github.com/tu_usuario/cb-auto-recorder.git
   cd cb-auto-recorder
   ```

2. **Configura un entorno virtual**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura `rclone`**:
   - Sigue las instrucciones oficiales de configuración de `rclone` para Google Drive.

5. **Actualiza las credenciales del bot**:
   - Rellena las variables en el archivo `config.py` o en el código:
     - `API_ID`, `API_HASH`, `BOT_TOKEN`.

---

## 🚀 **Uso**

1. **Ejecuta el bot**:
   ```bash
   python bot.py
   ```

2. **Comandos disponibles**:
   - `/grabar`: Inicia monitoreo y grabación automática.
   - `/clip`: Graba clips de 30 segundos.
   - `/check_modelo`: Lista modelos en grabación activa.
   - `/stop_grabacion`: Detiene una grabación activa y procesa el archivo.
   - `/mis_enlaces`: Muestra tus enlaces guardados.
   - `/eliminar_enlace`: Elimina un enlace guardado.
   - `/status`: Muestra el estado general del bot.
   - `/admin_reset`: Elimina archivos y reinicia procesos.

---

## 🖼️ **Capturas de Pantalla**

### Inicio del Bot
![Inicio](https://via.placeholder.com/800x400?text=Inicio+del+Bot)

### Monitoreo y Grabación
![Monitoreo](https://via.placeholder.com/800x400?text=Monitoreo+y+Grabación)

---

## 🤝 **Contribuciones**

¡Las contribuciones son bienvenidas! Sigue estos pasos:

1. Realiza un fork del proyecto.
2. Crea una rama de características: `git checkout -b feature/nueva-funcionalidad`.
3. Realiza tus cambios y haz commits: `git commit -m 'Agrega nueva funcionalidad'`.
4. Envía un pull request.

---

## ⚠️ **Licencia**

Este proyecto está bajo la licencia [MIT](LICENSE). Consulta el archivo `LICENSE` para más detalles.

---

## 🌟 **Agradecimientos**

- [Telethon](https://github.com/LonamiWebs/Telethon) por la API de Telegram.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) por la descarga de streams.
- [rclone](https://rclone.org/) por la gestión de subidas.

---

## 📬 **Contacto**

Si tienes preguntas, sugerencias o necesitas soporte, puedes contactarme en [Telegram](https://t.me/tu_usuario).
