import numpy as np
from a_estrella import a_estrella, LIBRE, ESTACION

# Grid simple 5x5
# 0 = LIBRE
# 2 = ESTACION (también transitable)
grid = np.array([
    [0, 0, 0, 0, 0],
    [0, 1, 1, 1, 0],  # obstáculos en medio
    [0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0],
    [0, 0, 0, 0, 2],  # estación
])

inicio = (0, 0)
meta = (4, 4)

ruta = a_estrella(grid, inicio, meta)

print("Ruta encontrada:")
print(ruta)

def valida_ruta(grid, ruta):
    if ruta is None or len(ruta) == 0:
        return False
    for (x,y) in ruta:
        if grid[y,x] not in (0,2):
            return False
    for (x0,y0),(x1,y1) in zip(ruta, ruta[1:]):
        if abs(x0-x1) + abs(y0-y1) != 1:
            return False
    return True

print("Ruta válida:", valida_ruta(grid, ruta))

def imprimir_grid_con_ruta(grid, ruta):
    g = grid.astype(str)
    g[g == '0'] = '.'
    g[g == '1'] = '#'
    g[g == '2'] = 'S'
    for x, y in ruta:
        if g[y, x] == '.':
            g[y, x] = 'o'
    for fila in g:
        print(" ".join(fila))

imprimir_grid_con_ruta(grid, ruta)
