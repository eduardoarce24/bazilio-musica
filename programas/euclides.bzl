### Máximo común divisor con el algoritmo de Euclides ###
Main |:
    <w> "Escribe dos numeros"
    <?> a
    <?> b
    Euclides a b
:|

Euclides a b |:
    while a /= b |:
        if a > b |:
            a <- a - b
        :| else |:
            b <- b - a
        :|
    :|
    <w> "Su MCD es" a
:|
