from tabla_reservas import TablaReservas

def prueba_basica():
    tabla = TablaReservas()

    # Caso 1: colisión de vértice (dos robots quieren la misma celda al mismo tick)
    tick_siguiente = 1
    celda_destino = (5, 5)

    tabla.reservar_celda(robot_id=0, celda=celda_destino, tick=tick_siguiente)
    libre = tabla.celda_libre(celda_destino, tick_siguiente)
    print("Caso 1 - celda libre después de reservar (esperado False):", libre)

    # Caso 2: swap A<->B (robot 0 quiere ir A->B y robot 1 quiere ir B->A al mismo tick)
    tabla = TablaReservas()
    A = (1, 1)
    B = (1, 2)
    tick_siguiente = 10

    # Robot 0 reserva su movimiento A->B
    assert tabla.puede_moverse(A, B, tick_siguiente) is True
    tabla.confirmar_movimiento(robot_id=0, actual=A, siguiente=B, tick_siguiente=tick_siguiente)

    # Robot 1 intenta el swap B->A en el mismo tick
    puede_swap = tabla.puede_moverse(B, A, tick_siguiente)
    print("Caso 2 - swap permitido (esperado False):", puede_swap)

    # Caso 3: movimiento normal sin conflicto
    tabla = TablaReservas()
    C = (2, 2)
    D = (2, 3)
    tick_siguiente = 7

    puede = tabla.puede_moverse(C, D, tick_siguiente)
    print("Caso 3 - movimiento normal permitido (esperado True):", puede)
    if puede:
        tabla.confirmar_movimiento(robot_id=0, actual=C, siguiente=D, tick_siguiente=tick_siguiente)
        print("Caso 3 - reservado OK")

if __name__ == "__main__":
    prueba_basica()
