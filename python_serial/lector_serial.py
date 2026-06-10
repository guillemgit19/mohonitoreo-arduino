import json
import time
import serial
import serial.tools.list_ports
import psycopg2
import psycopg2.extras
import sys
import os
import secrets

# Permite importar config.py desde la carpeta web
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web")))

from config import DB_CONFIG, SERIAL_PORT, SERIAL_BAUDRATE


# Archivo local donde se guarda el token de este Arduino/PC
DEVICE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "device_config.json")


def conectar_db():
    """
    Conecta con PostgreSQL.
    """
    return psycopg2.connect(**DB_CONFIG)


def clasificar_humedad(humedad):
    """
    Clasifica la humedad usando la misma lógica que Arduino y la web.
    """
    if humedad >= 70:
        return "ALTA"
    elif 40 <= humedad <= 69:
        return "NORMAL"
    else:
        return "BAJA"


def generar_device_token():
    """
    Genera un token único para identificar este Arduino conectado por cable.
    """
    return "dev_" + secrets.token_urlsafe(16)


def cargar_device_config():
    """
    Carga device_config.json si ya existe.
    """
    if not os.path.exists(DEVICE_CONFIG_PATH):
        return None

    with open(DEVICE_CONFIG_PATH, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_device_config(config):
    """
    Guarda device_config.json.
    """
    with open(DEVICE_CONFIG_PATH, "w", encoding="utf-8") as archivo:
        json.dump(config, archivo, indent=4)


def obtener_usuario_por_cedula(cedula):
    """
    Busca un usuario usando su cédula.
    """
    conn = conectar_db()

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT id, cedula, nombre, rol
            FROM usuarios
            WHERE cedula = %s
            """,
            (cedula,)
        )

        usuario = cur.fetchone()
        cur.close()

        return usuario

    finally:
        conn.close()


def registrar_dispositivo(usuario_id, nombre_dispositivo, device_token):
    """
    Registra el dispositivo en la base de datos.
    Si ya existe, no lo duplica.
    """
    conn = conectar_db()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO dispositivos (usuario_id, nombre, device_token)
            VALUES (%s, %s, %s)
            ON CONFLICT (device_token) DO NOTHING
            """,
            (usuario_id, nombre_dispositivo, device_token)
        )

        conn.commit()
        cur.close()

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()


def obtener_usuario_id_por_token(device_token):
    """
    Busca a qué usuario pertenece este dispositivo.
    """
    conn = conectar_db()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT usuario_id
            FROM dispositivos
            WHERE device_token = %s
            """,
            (device_token,)
        )

        resultado = cur.fetchone()
        cur.close()

        if not resultado:
            raise ValueError("El device_token no está registrado en la tabla dispositivos.")

        return resultado[0]

    finally:
        conn.close()


def verificar_y_resolver_usuario(config):
    """
    Valida token + cédula y devuelve el usuario_id donde se guardan las lecturas.
    El Arduino NO manda token; esto solo corre en la PC al iniciar lector_serial.py.
    """
    cedula = config.get("cedula", "").strip()
    token = config.get("device_token", "").strip()

    if not cedula:
        raise SystemExit("device_config.json no tiene 'cedula'.")

    usuario = obtener_usuario_por_cedula(cedula)
    if not usuario:
        raise SystemExit(
            f"No existe usuario con cédula {cedula}. "
            "Creá la cuenta en la web (Recibir contraseña) y volvé a configurar."
        )

    usuario_id = usuario["id"]
    print("--- Verificación de token (PC, no Arduino) ---")
    print(f"Cédula en config: {cedula} -> usuario_id={usuario_id} ({usuario['nombre']})")

    if not token:
        print("AVISO: sin device_token en JSON; se guarda solo por cédula.")
        return usuario_id

    try:
        uid_token = obtener_usuario_id_por_token(token)
    except ValueError:
        print(f"AVISO: token '{token}' no está en la BD. Registrándolo...")
        nombre = config.get("nombre_dispositivo") or f"Arduino de {usuario['nombre']}"
        registrar_dispositivo(usuario_id, nombre, token)
        uid_token = usuario_id

    if uid_token != usuario_id:
        print(
            f"AVISO: el token apunta a usuario_id={uid_token} "
            f"pero la cédula es usuario_id={usuario_id}."
        )
        print("Se usará la cédula del JSON para guardar lecturas.")
    else:
        print(f"Token '{token}' OK -> mismo usuario en BD.")

    print(f"Entrá a la web con cédula: {cedula}")
    print("----------------------------------------------")
    return usuario_id


def configurar_dispositivo_si_hace_falta():
    """
    Si no existe device_config.json, crea un token y pide la cédula del dueño.
    Esto se hace solo la primera vez.
    """
    config = cargar_device_config()

    if config:
        print("Configuración de dispositivo encontrada.")
        print(f"Device token: {config['device_token']}")
        print(f"Cédula asociada: {config['cedula']}")
        print()
        return config

    print("======================================")
    print(" CONFIGURACIÓN INICIAL DEL DISPOSITIVO")
    print("======================================")
    print("No se encontró device_config.json.")
    print("Vamos a asociar este Arduino/PC a un usuario.")
    print()

    cedula = input("Ingrese la cédula del dueño de este Arduino: ").strip()

    usuario = obtener_usuario_por_cedula(cedula)

    if not usuario:
        print()
        print("ERROR: No existe un usuario con esa cédula.")
        print("Primero creá el usuario desde la web en 'Recibir contraseña' o desde el panel admin.")
        raise SystemExit

    device_token = generar_device_token()
    nombre_dispositivo = f"Arduino de {usuario['nombre']}"

    registrar_dispositivo(usuario["id"], nombre_dispositivo, device_token)

    config = {
        "device_token": device_token,
        "cedula": usuario["cedula"],
        "nombre_usuario": usuario["nombre"],
        "nombre_dispositivo": nombre_dispositivo
    }

    guardar_device_config(config)

    print()
    print("Dispositivo configurado correctamente.")
    print(f"Usuario: {usuario['nombre']}")
    print(f"Cédula: {usuario['cedula']}")
    print(f"Device token generado: {device_token}")
    print()

    return config


def guardar_lectura(usuario_id, temperatura, humedad, estado_humedad):
    """
    Guarda una lectura asociada al usuario dueño del dispositivo.
    """
    conn = conectar_db()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO lecturas (usuario_id, temperatura, humedad, estado_humedad)
            VALUES (%s, %s, %s, %s)
            """,
            (usuario_id, temperatura, humedad, estado_humedad)
        )

        conn.commit()
        cur.close()

    except Exception as e:
        conn.rollback()
        print("Error guardando en PostgreSQL:")
        print(e)
        raise

    finally:
        conn.close()


def validar_datos(data):
    """
    Valida los datos que llegan desde Arduino.
    El Arduino no necesita mandar device_token.
    Python lo agrega automáticamente usando device_config.json.
    """
    if "temperatura" not in data:
        raise ValueError("Falta temperatura en el JSON")

    if "humedad" not in data:
        raise ValueError("Falta humedad en el JSON")

    temperatura = float(data["temperatura"])
    humedad = float(data["humedad"])

    if temperatura < -10 or temperatura > 60:
        raise ValueError("Temperatura fuera de rango")

    if humedad < 0 or humedad > 100:
        raise ValueError("Humedad fuera de rango")

    estado_humedad = clasificar_humedad(humedad)

    return temperatura, humedad, estado_humedad


def main():
    print("===================================")
    print(" LECTOR SERIAL DHT11 -> POSTGRESQL")
    print("===================================")
    puertos = [p.device for p in serial.tools.list_ports.comports()]
    print(f"Puerto serial (.env): {SERIAL_PORT}")
    print(f"Baudrate: {SERIAL_BAUDRATE}")
    print(f"Puertos detectados en esta PC: {puertos or '(ninguno)'}")

    if SERIAL_PORT not in puertos:
        print()
        print("AVISO: el puerto configurado no aparece conectado.")
        print("Actualizá SERIAL_PORT en .env (ej. COM5) y reiniciá este script.")
    print()

    config = configurar_dispositivo_si_hace_falta()

    usuario_id = verificar_y_resolver_usuario(config)

    print("Dispositivo listo.")
    print(f"Usuario ID interno: {usuario_id}")
    print(f"Dueño: {config['nombre_usuario']}")
    print(f"Token (solo PC): {config.get('device_token', '(sin token)')}")
    print()
    print("Presioná CTRL+C para detener.")
    print()

    try:
        arduino = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=2)
        time.sleep(2)

    except serial.SerialException as e:
        print(f"No se pudo abrir el puerto serial {SERIAL_PORT}")
        print("Revisá que:")
        print("- El Arduino esté conectado por USB")
        print("- SERIAL_PORT en .env coincida con el puerto real (Administrador de dispositivos)")
        print("- El Monitor Serial de Arduino IDE esté CERRADO")
        print("- No haya otra terminal con lector_serial.py ya abierta")
        print()
        if "Access is denied" in str(e) or "Acceso denegado" in str(e):
            print("El puerto existe pero está en uso por otro programa.")
        print(e)
        return
    except Exception as e:
        print(f"Error abriendo {SERIAL_PORT}: {e}")
        return

    while True:
        try:
            linea = arduino.readline().decode("utf-8", errors="ignore").strip()
            linea = linea.lstrip("\ufeff")

            if not linea:
                continue

            print(f"Recibido: {linea}")

            data = json.loads(linea)

            if data.get("error"):
                print(f"Arduino reportó error: {data.get('error')}")
                continue

            temperatura, humedad, estado_humedad = validar_datos(data)

            guardar_lectura(usuario_id, temperatura, humedad, estado_humedad)

            print(
                f"Guardado OK -> "
                f"Usuario ID: {usuario_id} | "
                f"Temperatura: {temperatura} °C | "
                f"Humedad: {humedad} % | "
                f"Estado: {estado_humedad}"
            )
            print("-----------------------------------")

        except json.JSONDecodeError:
            print("La línea recibida no es JSON válido.")

        except ValueError as e:
            print("Datos inválidos:")
            print(e)

        except KeyboardInterrupt:
            print("Programa detenido por el usuario.")
            break

        except Exception as e:
            print("Error general:")
            print(e)


if __name__ == "__main__":
    main()