
import sys

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


# ---------------------------------------------------------------- Paso 2.3
class Interprete(BazilioVisitor):
    def __init__(self, entrada=None, salida=None):
        self.marcos = [{}]  # pila de marcos (por ahora, uno solo)
        self._entrada = entrada if entrada is not None else sys.stdin
        self._tokens_entrada = []
        self._salida = salida if salida is not None else print

    @property
    def _vars(self):
        return self.marcos[-1]

    def ejecutar(self, arbol):
        for proc in arbol.procedimiento():
            if proc.PROC_ID().getText() == "Main":
                self.visit(proc.bloque())
                return
        raise ErrorBazilio("El programa no tiene un procedimiento Main.")

    # ------------------------------------------------------------ Paso 2.4
    def visitBloque(self, ctx):
        for instruccion in ctx.instruccion():
            self.visit(instruccion)

    def visitAsignacion(self, ctx):
        self._vars[ctx.VAR().getText()] = self.visit(ctx.expr())

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


# ---------------------------------------------------------------- Paso 2.7
def principal(argv):
    if len(argv) < 2:
        print("Uso: python bazilio_etapa3.py programa.bzl")
        return 2
    try:
        arbol = parsear(FileStream(argv[1], encoding="utf-8"))
        Interprete().ejecutar(arbol)
    except ErrorBazilio as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
