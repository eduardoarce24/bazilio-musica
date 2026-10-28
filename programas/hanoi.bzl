### Torres de Hanoi ###
Main |:
    <?> n
    Hanoi n 1 2 3
:|

Hanoi n ori dst aux |:
    if n > 0 |:
        Hanoi (n - 1) ori aux dst
        <w> ori "->" dst
        Hanoi (n - 1) aux dst ori
    :|
:|
