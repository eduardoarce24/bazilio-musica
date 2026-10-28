### Torres de Hanoi musicales: cada disco es una nota ###
Hanoi |:
    src <- {D C B A G}
    dst <- {}
    aux <- {}
    HanoiRec #src src dst aux
:|

HanoiRec n src dst aux |:
    if n > 0 |:
        HanoiRec (n - 1) src aux dst
        nota <- src[#src]
        8< src[#src]
        (:) nota
        dst << nota
        HanoiRec (n - 1) aux dst src
    :|
:|
