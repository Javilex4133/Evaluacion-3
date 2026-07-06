from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
import datetime
import serial
import threading

app = Flask(__name__)

# ========================================================
# CREDENCIALES DE SUPABASE
# ========================================================
SUPABASE_URL = "https://bbbttryqutlwqvnezibm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJiYnR0cnlxdXRsd3F2bmV6aWJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMyNzE5NzUsImV4cCI6MjA5ODg0Nzk3NX0.WLygOj67ntLQGWEWnSdC6kixKDNfgetBI1eQMWFzW9w"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================================================
# CONEXIÓN SERIAL A LA TARJETA 2 (ACTUADOR, CONECTADA POR USB)
# ========================================================
puertos_a_probar = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]
ser = None
lock_serial = threading.Lock()

for p in puertos_a_probar:
    try:
        ser = serial.Serial(p, 115200, timeout=1)
        print(f"[SERIAL] Conectado a la Tarjeta 2 (actuador) en {p}")
        break
    except Exception:
        continue

if not ser:
    print("[SERIAL ERROR] No se detectó la Tarjeta 2 por USB.")

estado_sistema = {
    "ultimo_log": "Servidor inicializado. Esperando datos de la Tarjeta 1...",
    "medida_actual": "Sin lecturas todavía."
}

def enviar_comando_led(comando):
    """Envía un solo caracter por Serial a la Tarjeta 2 para controlar los LEDs."""
    if ser:
        with lock_serial:
            ser.write(comando.encode('utf-8'))

def clasificar_distancia(distancia):
    """Determina qué LED corresponde según el rango de distancia (ajusta a tu gusto)."""
    if distancia < 10:
        return 'R'  # Rojo - cerca
    elif distancia < 25:
        return 'A'  # Amarillo - medio
    else:
        return 'V'  # Verde - lejos

# ========================================================
# ENDPOINT: RECIBE DATOS DE LA TARJETA 1 (SENSOR)
# ========================================================
@app.route("/api/lectura", methods=["POST"])
def recibir_lectura():
    datos = request.get_json()
    if not datos or "distancia" not in datos:
        return {"error": "Falta el campo 'distancia'"}, 400

    distancia = float(datos["distancia"])
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        supabase.table("mediciones").insert({
            "distancia": distancia,
            "created_at": fecha_actual
        }).execute()
    except Exception as e:
        estado_sistema["ultimo_log"] = f"Error al guardar en Supabase: {str(e)}"
        return {"error": str(e)}, 500

    comando = clasificar_distancia(distancia)
    enviar_comando_led(comando)

    estado_sistema["medida_actual"] = f"{distancia} cm"
    estado_sistema["ultimo_log"] = f"Lectura recibida y guardada a las {fecha_actual.split()[1]}. LED activado: {comando}"

    return {"status": "ok", "led": comando}, 200

# ========================================================
# ENDPOINT: ACTIVACIÓN MANUAL DESDE FLASK (BOTÓN WEB)
# ========================================================
@app.route("/actuar", methods=["POST"])
def actuar_manual():
    enviar_comando_led('X')  # Comando de alerta de prueba
    estado_sistema["ultimo_log"] = "Alerta manual disparada desde el panel de Flask."
    return redirect(url_for("index"))

# ========================================================
# VISTA PRINCIPAL
# ========================================================
@app.route("/", methods=["GET"])
def index():
    try:
        response = supabase.table("mediciones").select("*").order("created_at", desc=True).limit(5).execute()
        registros = response.data
    except Exception as e:
        registros = []
        estado_sistema["ultimo_log"] = f"Error al leer base de datos: {str(e)}"

    return render_template("index.html", logs=registros, estado=estado_sistema)

if __name__ == "__main__":
    # host="0.0.0.0" es OBLIGATORIO para que el ESP32 pueda alcanzar este servidor por red
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
