import nbimporter
from linearization import CallWrite, CallRead, CallCAS, CallDeq, CallEnq

testq1 = [
    [
        CallEnq(1, 1, 0, 2),
        CallDeq(1, 1, 2, 3),
        CallDeq(1, 2, 3, 4),
        CallDeq(1, 1, 4, 5),
        CallEnq(2, 1, 0, 1),
        CallEnq(2, 2, 1, 2),
    ],
    [
        CallEnq(1, 1, 0, 1),
        CallEnq(1, 2, 1, 2),
        CallEnq(1, 1, 2, 3),
        CallDeq(1, 1, 3, 5),
        CallDeq(2, 1, 3, 4),
        CallDeq(2, 2, 4, 5),
    ],
    [
        CallEnq(1, 1, 0, 1),
        CallEnq(1, 2, 1, 2),
        CallDeq(1, 1, 2, 3),
        CallEnq(2, 1, 0, 1),
        CallDeq(1, 2, 3, 4),
        CallDeq(2, 1, 1, 2),
    ]
]

testio = [
    [
        CallWrite(1, 1, 0, 2),
        CallRead(2, 1, 0, 2)
    ],
    [
        CallWrite(1, 1, 0.7, 1),
        CallWrite(2, 2, 0.5, 3),
        CallRead(1, 2, 1.5, 3),
        CallRead(3, 1, 1, 3)
    ],
    [
        CallWrite(1, 0, 0, 3),
        CallWrite(2, 1, 1, 5),
        CallRead(3, 1, 1.5, 2.5),
        CallRead(1, 0, 3, 4),
        CallRead(3, 1, 4, 5)
    ],
    [
        CallWrite(1, 0, 0, 1),
        CallWrite(2, 1, 1, 5),
        CallRead(3, 1, 1.5, 2.5),
        CallRead(1, 0, 2, 4),
        CallRead(2, 1, 5, 6)
    ],
    [
        CallWrite(1, 0, 0, 3),
        CallWrite(2, 1, 1, 2),
        CallRead(3, 0, 1.6, 5),
        CallRead(4, 1, 0, 1.5),
        CallRead(2, 1, 4, 5)
    ],
    [
        CallWrite(1, 0, 0, 3),
        CallWrite(2, 1, 1, 2.5),
        CallRead(3, 0, 2, 6),
        CallRead(2, 1, 4, 6),
    ],
    [
        CallWrite(4, 1, 5, 10),
        CallWrite(4, 0, 14, 24),
        CallWrite(3, 3, 4, 9),
        CallRead(4, 3, 29, 35)
    ],
    [
        CallWrite(1, 0, 0, 3),
        CallWrite(2, 1, 1, 2.5),
        CallRead(3, 0, 2, 6),
        CallRead(2, 1, 4, 6),
    ],
    [
        CallWrite(2, 4, 0, 9),
        CallWrite(2, 3, 10, 18),
        CallRead(2, 1, 23, 32),
        CallWrite(4, 1, 0, 10)
    ],
    [
        CallWrite(2, 0, 0, 8),
        CallWrite(2, 4, 11, 12),
        CallWrite(4, 1, 1, 10),
        CallRead(1, 4, 5, 11)
    ],
    [
        CallWrite(1, 1, 0, 2),
        CallWrite(2, 2, 3, 7),
        CallRead(1, 1, 4, 5),
    ],
    [
        CallWrite(4, 2, 0.29013142100511735, 2.1682983887584957),
        CallRead(4, 2, 4.39891968331108, 8.693148891876941),
        CallWrite(2, 0, 2.4230073653985653, 6.130926942326164),
        CallRead(3, 0, 3.530002948546454, 13.698999000690032)
    ],
    [
        CallWrite(1, 1, 0.8110039741682217, 3.0991766745613094),
        CallRead(1, 5, 7.7912794322245205, 15.582854156318602),
        CallRead(1, 1, 17.871960905346324, 22.409625561941137),
        CallRead(2, 1, 1.2971795543288045, 5.039186470922843),
        CallWrite(3, 5, 2.0095201496242323, 9.34758540075992)
    ]

]
