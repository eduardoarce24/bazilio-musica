"""Servidor web de Bazilio: convierte palabras en música.

Abre index.html en el navegador, recibe las palabras que escribes, las
convierte en un programa Bazilio (.bzl) y lo ejecuta con TU intérprete
(bazilio.py) para generar la partitura y el audio:
    .bzl  .ly  .pdf  .midi  .wav  .mp3

Uso (en la carpeta practica):
    python servidor.py
y abre http://localhost:8000  (se abre solo).

Solo usa la biblioteca estándar de Python: no hay que instalar nada más.
"""
import io
import json
import os
import re
import sys
import time
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from antlr4 import InputStream

import bazilio  # tu intérprete de la etapa 6

# En tu PC: localhost:8000. En un servidor (Render, Railway...) se usa la
# variable de entorno PORT y se escucha en todas las interfaces.
PUERTO = int(os.environ.get("PORT", 8000))
EN_LA_NUBE = "PORT" in os.environ
HOST = "0.0.0.0" if EN_LA_NUBE else "127.0.0.1"
HORAS_GUARDADO = 1          # en la nube se borran los archivos de más de 1 hora
CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "salida_web")
MAX_LETRAS = 200

TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".midi": "audio/midi",
    ".ly": "text/plain; charset=utf-8",
    ".bzl": "text/plain; charset=utf-8",
}


# ------------------------------------------------------------------ letras
def quitar_acentos(texto):
    """'Canción' -> 'Cancion', 'Ñandú' -> 'Nandu'."""
    normal = unicodedata.normalize("NFD", texto)
    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


def letra_a_nota(letra):
    """Convierte una letra en una nota de Bazilio (método francés).

    Las letras A-G ya son notas. Las demás siguen el abecedario en ciclos de
    siete: H=A, I=B, J=C ... O=A ... Cada ciclo sube o baja de octava para que
    la melodía no sea monótona:
        A-G -> octava 4    H-N -> octava 5    O-U -> octava 4    V-Z -> octava 5
    """
    i = ord(letra.upper()) - ord("A")          # 0..25
    nombre = "ABCDEFG"[i % 7]
    octava = 4 if (i // 7) % 2 == 0 else 5
    return f"{nombre}{octava}"


def palabras_a_bazilio(texto):
    """Devuelve (código Bazilio, lista de palabras con sus notas)."""
    limpio = quitar_acentos(texto)
    palabras = re.findall(r"[A-Za-z]+", limpio)
    detalle = [{"palabra": p, "notas": [letra_a_nota(c) for c in p]}
               for p in palabras]

    renglones = [
        "### Programa generado por servidor.py ###",
        f"### Texto original: {texto.strip()[:80].replace('#', '')} ###",
        "~~~ Cada letra es una nota: A-G son notas; las demas siguen el",
        "    abecedario en ciclos de siete (H=A, I=B, J=C ...) ~~~",
        "",
        "Main |:",
    ]
    for d in detalle:
        notas = " ".join(d["notas"])
        renglones.append(f'    <w> "{d["palabra"]}"')
        renglones.append(f"    (:) {{{notas}}}")
    renglones.append(":|")
    return "\n".join(renglones) + "\n", detalle


# ------------------------------------------------------------ modo notas
_NOTA = re.compile(r"([A-Ga-g])([0-8]?)")


def leer_notas(texto):
    """'C4 D4, e4 B3A3' -> ['C4', 'D4', 'E4', 'B3', 'A3'].

    Acepta notas separadas por espacios, comas o escritas juntas. Sin número
    es la octava 4 (como en Bazilio). Avisa si algo no es una nota o si la nota
    no existe en el piano (A0 a C8).
    """
    notas = []
    pos = 0
    for m in _NOTA.finditer(texto):
        sobrante = texto[pos:m.start()]
        if sobrante.strip(" ,;|-\t\n\r"):
            raise ValueError(f"«{sobrante.strip()}» no es una nota. Usa letras A-G "
                             "con un número de octava opcional, por ejemplo C4 D4 B3.")
        nota = m.group(1).upper() + m.group(2)
        bazilio.valor_nota(nota)          # valida el rango del piano
        notas.append(nota)
        pos = m.end()
    if texto[pos:].strip(" ,;|-\t\n\r"):
        raise ValueError(f"«{texto[pos:].strip()}» no es una nota. Usa letras A-G "
                         "con un número de octava opcional, por ejemplo C4 D4 B3.")
    return notas


def notas_a_bazilio(texto):
    """Devuelve (código Bazilio, detalle) para una melodía escrita con notas."""
    notas = leer_notas(texto)
    renglones = [
        "### Programa generado por servidor.py (modo notas) ###",
        "",
        "Main |:",
        '    <w> "Melodia"',
    ]
    for i in range(0, len(notas), 8):     # 8 notas por renglón, como en la partitura
        renglones.append("    (:) {" + " ".join(notas[i:i + 8]) + "}")
    renglones.append(":|")
    detalle = [{"palabra": "melodia", "notas": notas}] if notas else []
    return "\n".join(renglones) + "\n", detalle


# ------------------------------------------------------------- conversión
def parece_notas(texto):
    """True si el texto son solo notas y al menos una trae octava: 'C4 D4 B3'."""
    return (re.fullmatch(r"[\s,;|-]*(?:[A-Ga-g][0-8]?[\s,;|-]*)+", texto) is not None
            and re.search(r"[A-Ga-g][0-8]", texto) is not None)


def convertir(texto, modo="palabras"):
    if modo != "notas" and parece_notas(texto):
        modo = "notas"      # escribiste notas con octava: se respetan las octavas
    if modo == "notas":
        codigo, detalle = notas_a_bazilio(texto)
        if not detalle:
            raise ValueError("Escribe al menos una nota, por ejemplo: C4 D4 E4.")
    else:
        codigo, detalle = palabras_a_bazilio(texto)
        if not detalle:
            raise ValueError("Escribe al menos una palabra con letras.")
    if sum(len(d["notas"]) for d in detalle) > MAX_LETRAS:
        raise ValueError(f"Máximo {MAX_LETRAS} letras por canción.")

    os.makedirs(SALIDA, exist_ok=True)
    limpiar_viejos()
    nombre = re.sub(r"[^a-z0-9]+", "_", "_".join(d["palabra"] for d in detalle).lower())[:30]
    nombre = f"{nombre}_{time.strftime('%H%M%S')}"
    base = os.path.join(SALIDA, nombre)

    with open(base + ".bzl", "w", encoding="utf-8") as f:
        f.write(codigo)

    # ejecutar el programa con el intérprete de la práctica
    escrito = []
    avisos = []
    arbol = bazilio.parsear(InputStream(codigo))
    interprete = bazilio.Interprete(entrada=io.StringIO(""), salida=escrito.append)
    interprete.cargar(arbol)
    interprete.ejecutar("Main")
    archivos = [base + ".bzl"] + bazilio.generar_salida(
        interprete.partitura, base, aviso=avisos.append)

    return {
        "codigo": codigo,
        "detalle": detalle,
        "pantalla": escrito,
        "avisos": avisos,
        "total": len(interprete.partitura),
        "archivos": [os.path.basename(a) for a in archivos if os.path.exists(a)],
    }


def limpiar_viejos():
    """Borra archivos generados hace más de HORAS_GUARDADO (solo en la nube)."""
    if not EN_LA_NUBE:
        return
    limite = time.time() - HORAS_GUARDADO * 3600
    for nombre in os.listdir(SALIDA):
        ruta = os.path.join(SALIDA, nombre)
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
        except OSError:
            pass


# ------------------------------------------------------------- servidor
class Manejador(BaseHTTPRequestHandler):
    def _enviar(self, codigo, cuerpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo, datos):
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta in ("/", "/index.html"):
            with open(os.path.join(CARPETA, "index.html"), "rb") as f:
                self._enviar(200, f.read(), TIPOS[".html"])
            return
        if ruta.startswith("/salida/"):
            nombre = os.path.basename(ruta)            # evita salir de la carpeta
            archivo = os.path.join(SALIDA, nombre)
            ext = os.path.splitext(nombre)[1]
            if os.path.isfile(archivo) and ext in TIPOS:
                with open(archivo, "rb") as f:
                    self._enviar(200, f.read(), TIPOS[ext])
                return
        self._enviar(404, "No encontrado".encode("utf-8"), "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/convertir":
            self._enviar(404, b"", "text/plain")
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if largo > 10_000:
                raise ValueError("Texto demasiado largo.")
            datos = json.loads(self.rfile.read(largo).decode("utf-8"))
            self._json(200, convertir(datos.get("texto", ""), datos.get("modo", "palabras")))
        except (ValueError, bazilio.ErrorBazilio) as e:
            self._json(400, {"error": str(e)})
        except Exception as e:  # cualquier otro problema se muestra en la página
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, formato, *args):
        sys.stderr.write("  " + (formato % args) + "\n")


def principal():
    url = f"http://localhost:{PUERTO}"
    servidor = ThreadingHTTPServer((HOST, PUERTO), Manejador)
    print(f"Servidor de Bazilio en {url}" if not EN_LA_NUBE
          else f"Servidor de Bazilio escuchando en el puerto {PUERTO}", flush=True)
    print("Los archivos se guardan en la carpeta salida_web")
    print("Para detenerlo presiona Ctrl + C", flush=True)
    if not EN_LA_NUBE:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    principal()
