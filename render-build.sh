#!/usr/bin/env bash

# Actualiza los paquetes y sistema
apt-get update && apt-get install -y ffmpeg

# Instala los requerimientos de Python
pip install -r requirements.txt
