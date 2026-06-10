"""
Prueba rápida: lee 5 líneas del Arduino sin guardar en la base.
Cerrá el Monitor Serial de Arduino IDE antes de ejecutar.

  python probar_serial.py
"""
import time

import serial
import serial.tools.list_ports

from web.config import SERIAL_BAUDRATE, SERIAL_PORT


def main():
    puertos = [p.device for p in serial.tools.list_ports.comports()]
    print("Puertos USB detectados:", puertos or "(ninguno)")
    print(f"Usando .env -> {SERIAL_PORT} @ {SERIAL_BAUDRATE} baud")
    print()

    if SERIAL_PORT not in puertos:
        print(f"ERROR: {SERIAL_PORT} no está en la lista. Corregí SERIAL_PORT en .env")
        return

    try:
        arduino = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=3)
    except serial.SerialException as e:
        print("No se pudo abrir el puerto:", e)
        print("Cerrá Arduino IDE (Monitor Serial) y cualquier lector_serial.py abierto.")
        return

    print("Conectado. Esperando datos del Arduino (5 líneas)...")
    time.sleep(2)

    for i in range(5):
        linea = arduino.readline().decode("utf-8", errors="ignore").strip()
        print(f"  [{i + 1}] {linea!r}")

    arduino.close()
    print()
    print("Si ves JSON con temperatura/humedad, el Arduino está bien.")
    print("Siguiente paso: python python_serial\\lector_serial.py")


if __name__ == "__main__":
    main()
