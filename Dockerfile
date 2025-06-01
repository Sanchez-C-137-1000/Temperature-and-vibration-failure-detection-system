# Imagen base de Python
FROM python:3.10-slim

# Instala dependencias del sistema para Kivy
RUN apt-get update && apt-get install -y \
    python3-pip \
    build-essential \
    python3-dev \
    ffmpeg \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libgl1-mesa-glx \
    libgles2-mesa-dev \
    libmtdev-dev \
    x11-xserver-utils \
    libgstreamer1.0 \
    libgstreamer1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    && apt-get clean

# Crea directorio para el código
WORKDIR /app

# Copia archivos al contenedor
COPY . /app

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Comando para ejecutar la app
CMD ["python", "app/main.py"]
