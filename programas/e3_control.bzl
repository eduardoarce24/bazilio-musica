Main |:
    ### cuenta regresiva ###
    x <- 3
    while x > 0 |:
        <w> x
        x <- x - 1
    :|
    <w> "Despegue"
    ### máximo común divisor de 12 y 18 ###
    a <- 12
    b <- 18
    while a /= b |:
        if a > b |:
            a <- a - b
        :| else |:
            b <- b - a
        :|
    :|
    <w> "MCD:" a
:|
