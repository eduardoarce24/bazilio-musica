### Operaciones con listas ###
Main |:
    l <- {10 20 30}
    <w> "Lista:" l "longitud:" #l
    <w> "Segundo elemento:" l[2]
    l << 40
    <w> "Después de añadir 40:" l
    8< l[1]
    <w> "Después de recortar el primero:" l
    copia <- l
    copia << 99
    <w> "l no cambia al modificar la copia:" l
    Agrega l 77
    <w> "Las listas se pasan por referencia:" l
:|

Agrega lista x |:
    lista << x
:|
