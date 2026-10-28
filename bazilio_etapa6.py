
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import wave

from antlr4 import CommonTokenStream, FileStream
from antlr4.error.ErrorListener import ErrorListener

from BazilioLexer import BazilioLexer
from BazilioParser import BazilioParser
from BazilioVisitor import BazilioVisitor


# ---------------------------------------------------------------- Paso 2.1
class ErrorBazilio(Exception):
    """Error de sintaxis o de ejecución de un programa Bazilio."""


class _ListenerErrores(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ErrorBazilio(
            f"Error de sintaxis en la línea {line}, columna {column}: {msg}")


def parsear(flujo):
    lexer = BazilioLexer(flujo)
    lexer.removeErrorListeners()
    lexer.addErrorListener(_ListenerErrores())
    parser = BazilioParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(_ListenerErrores())
    return parser.programa()


# ---------------------------------------------------------------- Paso 2.2
def _div_c(a, b):
    """División entera con truncamiento hacia cero, como en C."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


# ---------------------------------------------------------------- Paso 5.1
# las teclas blancas del piano: A0 = 0, B0 = 1, C1 = 2 ... C8 = 51
NOTA_MIN, NOTA_MAX = 0, 51
_POSICION = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def valor_nota(texto):
    """'C4' -> 23, 'C' -> 23 (Do central), 'A0' -> 0, 'C8' -> 51."""
    letra = texto[0]
    octava = int(texto[1]) if len(texto) == 2 else 4
    if octava == 0:
        if letra not in "AB":
            raise ErrorBazilio(f"La nota {texto} no existe en el piano "
                               "(la octava 0 solo tiene A0 y B0).")
        return 0 if letra == "A" else 1
    valor = 2 + 7 * (octava - 1) + _POSICION[letra]
    if valor > NOTA_MAX:
        raise ErrorBazilio(
            f"La nota {texto} no existe en el piano (la última es C8).")
    return valor


# ---------------------------------------------------------------- Paso 2.3
class Interprete(BazilioVisitor):
    # ------------------------------------------------------------ Paso 4.1
    def __init__(self, entrada=None, salida=None):
        self.procedimientos = {}  # nombre -> (parámetros, bloque)
        self.marcos = []          # pila de variables: un diccionario por llamada
        self._entrada = entrada if entrada is not None else sys.stdin
        self._tokens_entrada = []
        self._salida = salida if salida is not None else print
        self.partitura = []       # Paso 6.2: valores de las notas tocadas, en orden

    @property
    def _vars(self):
        return self.marcos[-1]

    def cargar(self, arbol):
        for proc in arbol.procedimiento():
            nombre = proc.PROC_ID().getText()
            params = [v.getText() for v in proc.VAR()]
            if nombre in self.procedimientos:
                raise ErrorBazilio(
                    f"El procedimiento {nombre} está definido más de una vez.")
            if len(set(params)) != len(params):
                raise ErrorBazilio(f"El procedimiento {nombre} repite nombres "
                                   "de parámetros formales.")
            self.procedimientos[nombre] = (params, proc.bloque())

    def ejecutar(self, inicio="Main"):
        self._llamar(inicio, [])

    def _llamar(self, nombre, valores):
        if nombre not in self.procedimientos:
            raise ErrorBazilio(
                f"Se llamó al procedimiento {nombre}, que no está definido.")
        params, bloque = self.procedimientos[nombre]
        if len(params) != len(valores):
            raise ErrorBazilio(f"{nombre} espera {len(params)} parámetro(s) "
                               f"y recibió {len(valores)}.")
        # un marco nuevo por cada invocación
        self.marcos.append(dict(zip(params, valores)))
        try:
            self.visit(bloque)
        finally:
            # al terminar, el marco desaparece
            self.marcos.pop()

    def visitInvocacion(self, ctx):
        valores = [self.visit(e) for e in ctx.expr()]
        self._llamar(ctx.PROC_ID().getText(), valores)

    # ------------------------------------------------------------ Paso 2.4
    def visitBloque(self, ctx):
        for instruccion in ctx.instruccion():
            self.visit(instruccion)

    def visitAsignacion(self, ctx):  # Paso 5.2
        valor = self.visit(ctx.expr())
        if isinstance(valor, list):
            valor = list(valor)  # asignar una lista copia sus valores
        self._vars[ctx.VAR().getText()] = valor

    def visitLectura(self, ctx):
        self._vars[ctx.VAR().getText()] = self._leer_entero()

    def visitEscritura(self, ctx):
        partes = []
        for hijo in list(ctx.getChildren())[1:]:  # el primero es <w>
            if hasattr(hijo, "symbol"):  # es un TEXTO
                partes.append(hijo.getText()[1:-1])
            else:
                partes.append(self._formatear(self.visit(hijo)))
        self._salida(" ".join(partes))

    # ------------------------------------------------------------ Paso 3.1
    def visitCondicional(self, ctx):
        bloques = ctx.bloque()
        if self._verdadero(self.visit(ctx.expr())):
            self.visit(bloques[0])
        elif len(bloques) > 1:  # el else es optativo
            self.visit(bloques[1])

    def visitIteracion(self, ctx):
        while self._verdadero(self.visit(ctx.expr())):
            self.visit(ctx.bloque())

    # ------------------------------------------------------------ Paso 3.2
    @staticmethod
    def _verdadero(valor):
        if isinstance(valor, list):
            raise ErrorBazilio("Una condición debe ser un entero "
                               "(0 es falso, otro valor es verdadero).")
        return valor != 0

    # ------------------------------------------------------------ Paso 2.5
    def visitEntero(self, ctx):
        return int(ctx.getText())

    def visitVariable(self, ctx):
        return self._vars.get(ctx.getText(), 0)  # sin valor todavía = 0

    def visitParentesis(self, ctx):
        return self.visit(ctx.expr())

    def visitMulDiv(self, ctx):
        a, b = self._operandos(ctx)
        op = ctx.op.text
        if op == "*":
            return a * b
        if b == 0:
            raise ErrorBazilio("División por cero.")
        q = _div_c(a, b)
        return q if op == "/" else a - b * q

    def visitSumaResta(self, ctx):
        a, b = self._operandos(ctx)
        return a + b if ctx.op.text == "+" else a - b

    def visitRelacional(self, ctx):
        a, b = self._operandos(ctx)
        return int({"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[ctx.op.text])

    def visitIgualdad(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        return int((a == b) if ctx.op.text == "=" else (a != b))

    # ------------------------------------------------------------ Paso 6.3
    def visitReproduccion(self, ctx):
        valor = self.visit(ctx.expr())
        for nota in (valor if isinstance(valor, list) else [valor]):
            nota_a_lilypond(nota)  # valida que esté en el rango del piano
            self.partitura.append(nota)

    # ------------------------------------------------------------ Paso 5.3
    def visitNota(self, ctx):
        return valor_nota(ctx.getText())

    def visitLista(self, ctx):
        elementos = [self.visit(e) for e in ctx.expr()]
        if any(isinstance(e, list) for e in elementos):
            raise ErrorBazilio("Las listas solo pueden contener enteros o notas.")
        return elementos

    def visitLongitud(self, ctx):
        valor = self.visit(ctx.expr())
        if not isinstance(valor, list):
            raise ErrorBazilio("El operador # solo se puede aplicar a una lista.")
        return len(valor)

    def visitIndice(self, ctx):
        base = self.visit(ctx.expr(0))
        if not isinstance(base, list):
            raise ErrorBazilio("Solo se puede consultar un índice en una lista.")
        i = self._entero(self.visit(ctx.expr(1)))
        self._comprobar_indice(ctx.expr(0).getText(), base, i)
        return base[i - 1]  # los índices empiezan en 1

    def visitAgregado(self, ctx):
        nombre = ctx.VAR().getText()
        lista = self._vars.get(nombre, 0)
        if not isinstance(lista, list):
            raise ErrorBazilio(f"{nombre} no es una lista: "
                               "no se puede usar << con ella.")
        valor = self.visit(ctx.expr())
        if isinstance(valor, list):
            raise ErrorBazilio("Las listas solo pueden contener enteros o notas.")
        lista.append(valor)

    def visitCorte(self, ctx):
        nombre = ctx.VAR().getText()
        lista = self._vars.get(nombre, 0)
        if not isinstance(lista, list):
            raise ErrorBazilio(f"{nombre} no es una lista: "
                               "no se puede usar 8< con ella.")
        i = self._entero(self.visit(ctx.expr()))
        self._comprobar_indice(nombre, lista, i)
        del lista[i - 1]

    @staticmethod
    def _comprobar_indice(nombre, lista, i):
        n = len(lista)
        if not 1 <= i <= n:
            raise ErrorBazilio(
                f"Índice {i} inexistente en {nombre} (la lista tiene {n} "
                f"elemento(s); los índices van de 1 a {n}).")

    # ------------------------------------------------------------ Paso 2.6
    @staticmethod
    def _entero(valor):
        if isinstance(valor, list):
            raise ErrorBazilio("Se esperaba un entero y se encontró una lista.")
        return valor

    def _operandos(self, ctx):
        izquierda = self._entero(self.visit(ctx.expr(0)))
        derecha = self._entero(self.visit(ctx.expr(1)))
        return izquierda, derecha

    @staticmethod
    def _formatear(valor):
        if isinstance(valor, list):
            return "[" + " ".join(str(x) for x in valor) + "]"
        return str(valor)

    def _leer_entero(self):
        while not self._tokens_entrada:
            linea = self._entrada.readline()
            if linea == "":
                raise ErrorBazilio(
                    "Se esperaba un entero en la entrada, pero ya no hay más datos.")
            self._tokens_entrada = linea.split()
        token = self._tokens_entrada.pop(0)
        try:
            return int(token)
        except ValueError:
            raise ErrorBazilio(
                f"Se esperaba un entero en la entrada y se leyó «{token}».")


# ---------------------------------------------------------------- Paso 6.4
def nota_a_lilypond(valor):
    """Valor 0..51 -> LilyPond absoluto, duración de negra (p. ej. c'4)."""
    if not NOTA_MIN <= valor <= NOTA_MAX:
        raise ErrorBazilio(
            f"Se intentó tocar el valor {valor}, fuera del rango del piano (0 a 51).")
    if valor < 2:
        letra, octava = ("a", "b")[valor], 0
    else:
        k = valor - 2
        octava, letra = 1 + k // 7, "cdefgab"[k % 7]
    marcas = "'" * (octava - 3) if octava > 3 else "," * (3 - octava)
    return f"{letra}{marcas}4"


def version_lilypond():
    try:
        salida = subprocess.run(["lilypond", "--version"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace").stdout
        return re.search(r"(\d+\.\d+\.\d+)", salida).group(1)
    except (OSError, AttributeError):
        return "2.20.0"


def texto_lilypond(partitura, tempo=120):
    notas = [nota_a_lilypond(v) for v in partitura]
    renglones = [" ".join(notas[i:i + 8]) for i in range(0, len(notas), 8)]
    cuerpo = "\n".join("    " + r for r in renglones)
    return (f'\\version "{version_lilypond()}"\n'
            "\\score {\n"
            "  \\absolute {\n"
            f"    \\tempo 4 = {tempo}\n"
            f"{cuerpo}\n"
            "  }\n"
            "  \\layout { }\n"
            "  \\midi { }\n"
            "}\n")


# ------------------------------------------- Agregado para Windows (sin TiMidity)
_SEMITONO = [0, 2, 4, 5, 7, 9, 11]  # c d e f g a b


def nota_a_midi(valor):
    """Valor Bazilio (0..51) -> número MIDI (A0 = 21, C4 = 60, C8 = 108)."""
    if valor < 2:
        return 21 if valor == 0 else 23
    k = valor - 2
    octava, pos = 1 + k // 7, k % 7
    return 12 * (octava + 1) + _SEMITONO[pos]


def sintetizar_wav(partitura, ruta_wav, tempo=120, frecuencia=44100):
    """Genera un WAV parecido a un piano sencillo: cada nota dura una negra."""
    dur = 60.0 / tempo                 # segundos por negra
    n = int(frecuencia * dur)
    cuadros = bytearray()
    for valor in partitura:
        f = 440.0 * 2 ** ((nota_a_midi(valor) - 69) / 12)
        for i in range(n):
            t = i / frecuencia
            env = math.exp(-3.0 * t) * min(1.0, t * 200)       # ataque y caída
            if i > n - 400:                                     # evita chasquidos
                env *= (n - i) / 400
            s = (math.sin(2 * math.pi * f * t)
                 + 0.5 * math.sin(4 * math.pi * f * t)
                 + 0.25 * math.sin(6 * math.pi * f * t)) / 1.75
            cuadros += struct.pack("<h", int(30000 * 0.8 * env * s))
    cuadros += b"\x00\x00" * (frecuencia // 2)                 # medio segundo final
    with wave.open(ruta_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(bytes(cuadros))


def generar_salida(partitura, base, solo_ly=False, aviso=print):
    """Escribe base.ly y convierte con las herramientas externas que haya instaladas."""
    ruta_ly = base + ".ly"
    with open(ruta_ly, "w", encoding="utf-8") as f:
        f.write(texto_lilypond(partitura))
    generados = [ruta_ly]
    if solo_ly:
        return generados

    def correr(cmd, descripcion):
        if shutil.which(cmd[0]) is None:
            aviso(f"Aviso: no se encontró «{cmd[0]}», no se generó {descripcion}.")
            return False
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            detalle = (r.stderr or "").strip()[-400:]
            aviso(f"Aviso: falló {cmd[0]} al generar {descripcion}:\n{detalle}")
            return False
        return True

    # 1) LilyPond: PDF y MIDI (en Windows forzamos la extensión .midi)
    if not correr(["lilypond", "-dmidi-extension=midi", "-o", base, ruta_ly],
                  "el PDF y el MIDI"):
        return generados
    generados += [base + ".pdf", base + ".midi"]

    # 2) WAV: con TiMidity++ si está instalado; si no, con Python
    if shutil.which("timidity") is not None:
        if not correr(["timidity", "-Ow", "-o", base + ".wav", base + ".midi"], "el WAV"):
            return generados
    else:
        sintetizar_wav(partitura, base + ".wav")
    generados.append(base + ".wav")

    # 3) ffmpeg: MP3
    if correr(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".wav",
               "-codec:a", "libmp3lame", "-qscale:a", "2", base + ".mp3"], "el MP3"):
        generados.append(base + ".mp3")
    return generados


# ---------------------------------------------------------------- Paso 6.5
def principal(argv):
    solo_ly = "--solo-ly" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("Uso: python bazilio.py programa.bzl [Procedimiento] [--solo-ly]")
        return 2
    ruta = args[0]
    inicio = args[1] if len(args) > 1 else "Main"
    try:
        arbol = parsear(FileStream(ruta, encoding="utf-8"))
        interprete = Interprete()
        interprete.cargar(arbol)
        interprete.ejecutar(inicio)
        if interprete.partitura:
            base = os.path.splitext(ruta)[0]
            archivos = generar_salida(interprete.partitura, base, solo_ly=solo_ly,
                                      aviso=lambda m: print(m, file=sys.stderr))
            nombres = ", ".join(os.path.basename(a) for a in archivos)
            print("Archivos generados: " + nombres, file=sys.stderr)
    except ErrorBazilio as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(200000)
    # para recursividad profunda; si Windows no acepta 512 MB, se usa 256 MB
    for megas in (512, 256, 64):
        try:
            threading.stack_size(megas * 1024 * 1024)
            break
        except (ValueError, RuntimeError):
            continue
    resultado = []
    hilo = threading.Thread(target=lambda: resultado.append(principal(sys.argv)))
    hilo.start()
    hilo.join()
    sys.exit(resultado[0] if resultado else 1)
