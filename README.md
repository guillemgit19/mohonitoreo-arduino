# Monitoreo Arduino - Captura de Temperatura y Humedad (DHT11)

Este repositorio contiene el código de hardware y el script listener para capturar lecturas de sensores de temperatura y humedad y enviarlos a la base de datos PostgreSQL.

## 📁 Estructura
- `arduino/`: Código `.ino` para cargar en tu placa Arduino (utiliza sensores DHT11 y pantalla LCD I2C).
- `python_serial/`: Script en Python (`lector_serial.py`) que escucha el puerto COM/USB de la PC y registra las lecturas JSON en la base de datos PostgreSQL de forma automatizada.
- `probar_serial.py`: Script de prueba rápida para testear la comunicación serial con tu Arduino.
- `verificar_sistema.py`: Herramienta de diagnóstico para verificar que los tokens de tus dispositivos y cédulas coincidan correctamente con la base de datos.

## 🚀 Cómo correr el Lector Serial
1. Conecta tu Arduino por USB.
2. Abre una terminal en esta carpeta.
3. Crea un entorno virtual e instala los requerimientos:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. Configura tu archivo `.env` en la raíz (puedes tomar de base el del repositorio Web) con el puerto COM de tu Arduino (ej. `SERIAL_PORT=COM5`).
5. Corre el daemon:
   ```bash
   python python_serial/lector_serial.py
   ```
