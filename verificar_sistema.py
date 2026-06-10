"""
Diagnóstico: tokens, base de datos y puerto serial.
Ejecutar:  python verificar_sistema.py
"""
import json
import os

import psycopg2
import serial.tools.list_ports

from web.config import DB_CONFIG, SERIAL_PORT, SERIAL_BAUDRATE

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "python_serial", "device_config.json"
)


def ok(msg):
    print(f"  OK  {msg}")


def fail(msg):
    print(f"  X   {msg}")


def main():
    print("=== VERIFICACIÓN SISTEMA DHT ===\n")

    # 1. device_config.json
    print("1) Archivo device_config.json")
    if not os.path.exists(CONFIG_PATH):
        fail(f"No existe: {CONFIG_PATH}")
        print("     Corré: python python_serial\\lector_serial.py (primera vez)")
        return
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    token_archivo = config.get("device_token")
    cedula = config.get("cedula")
    ok(f"Token en archivo: {token_archivo}")
    ok(f"Cédula dueño: {cedula} ({config.get('nombre_usuario')})")

    # 2. Base de datos
    print("\n2) Tokens en PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, usuario_id, device_token FROM dispositivos WHERE device_token = %s",
        (token_archivo,),
    )
    fila = cur.fetchone()
    if not fila:
        fail(f"El token '{token_archivo}' NO está en tabla dispositivos")
        print("     Solución: borrá device_config.json y volvé a configurar,")
        print("     o insertá el dispositivo desde el panel admin.")
    else:
        ok(f"Token en BD -> dispositivo id={fila[0]}, usuario_id={fila[1]}")

    cur.execute("SELECT id, nombre FROM usuarios WHERE cedula = %s", (cedula,))
    usuario = cur.fetchone()
    if not usuario:
        fail(f"No hay usuario con cédula {cedula}")
    else:
        uid, nombre = usuario
        ok(f"Usuario en BD: id={uid}, nombre={nombre}")
        if fila and fila[1] != uid:
            fail(f"Token ligado a usuario_id={fila[1]} pero cédula es id={uid}")
        elif fila:
            ok("Token y cédula coinciden con el mismo usuario")

    cur.execute("SELECT COUNT(*), MAX(timestamp) FROM lecturas WHERE usuario_id = %s", (uid if usuario else -1,))
    count, ultima = cur.fetchone()
    print(f"\n3) Lecturas del dueño (usuario_id={uid if usuario else '?'})")
    print(f"     Total: {count} | Última: {ultima or '(ninguna)'}")
    if count == 0:
        fail("No hay lecturas para este usuario en la BD")
    elif ultima:
        ok("Hay al menos una lectura guardada")

    cur.execute("SELECT COUNT(*) FROM lecturas")
    total_global = cur.fetchone()[0]
    if total_global > count:
        print(f"     Nota: hay {total_global - count} lectura(s) de OTROS usuarios.")
        print("     En la web tenés que entrar con cédula", cedula)

    conn.close()

    # 4. Puerto serial
    print("\n4) Puerto USB / Arduino")
    puertos = [p.device for p in serial.tools.list_ports.comports()]
    print(f"     Puertos detectados: {puertos or '(NINGUNO - Arduino desconectado?)'}")
    print(f"     .env SERIAL_PORT = {SERIAL_PORT} @ {SERIAL_BAUDRATE}")
    if not puertos:
        fail("No hay puertos COM. Conectá el Arduino por USB.")
    elif SERIAL_PORT not in puertos:
        fail(f"{SERIAL_PORT} no está en la lista. Actualizá .env")
    else:
        ok(f"{SERIAL_PORT} aparece conectado")

    print("\n=== CONCLUSIÓN ===")
    if fila and usuario and fila[1] == usuario[0]:
        print("Los TOKENS están bien. El problema suele ser:")
        print("  - Arduino sin USB o Monitor Serial abierto")
        print("  - lector_serial.py no está corriendo")
        print("  - Entraste a la web con otro usuario (no", cedula + ")")
        print("\nProbá: python probar_serial.py  (con Arduino conectado)")
    else:
        print("Hay un problema de configuración de token/usuario arriba.")


if __name__ == "__main__":
    main()
