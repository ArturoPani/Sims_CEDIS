import json
from sim_core import Pedido, SimAlmacen, SimConfig, cargar_layout

grid, estacion_dock, anaquel_home, spawns = cargar_layout(
    'outputs/prueba_150_6000/layout.npy',
    'outputs/prueba_150_6000/estaciones.json',
    'outputs/prueba_150_6000/anaqueles.json',
    'outputs/prueba_150_6000/spawn.json',
)

with open('outputs/prueba_150_6000/pedidos.json', 'r') as f:
    raw = json.load(f)
pedidos = [Pedido(
    pedido_id=p['pedido_id'],
    anaquel_id=p['anaquel_id'],
    estacion_id=p['estacion_id'],
    tick_creacion=p['tick_creacion'],
) for p in raw['pedidos']]

sim = SimAlmacen(
    grid=grid,
    estacion_dock=estacion_dock,
    anaquel_home=anaquel_home,
    robots=150,
    puntos_spawn=spawns[:150],
    pedidos=pedidos,
    seed=12,
    config=SimConfig(),
)

print('Corriendo 10000 ticks...')
sim.run(10000)

m = sim.metricas()
print(json.dumps(m, indent=2))

with open('outputs/prueba_150_6000/metricas.json', 'w', encoding='utf-8') as f:
    json.dump(m, f, indent=2, ensure_ascii=False)
print('\nGuardado en outputs/prueba_150_6000/metricas.json\n')

ref = {
    'pedidos_completados': 5943,
    'tiempo_promedio_pedido_ticks': 3927.51,
    'throughput_pedidos_por_1000_ticks': 594.3,
    'tiempo_promedio_espera_ticks': 2343.35,
    'utilizacion_promedio': 0.8551,
    'colisiones_vertice': 0,
    'intercambios_arista': 0,
    'deadlock': 2152,
    'eventos_alto': 351502,
    'distancia_total_celdas': 925208,
    'relevos': 0,
}

keys = list(ref.keys())
header = f"{'Metrica':<40} {'Referencia':>15} {'Obtenido':>15} {'Diferencia':>15}"
print(header)
print('-' * len(header))
for k in keys:
    r = ref.get(k)
    o = m.get(k, 'N/A')
    if r is None or o == 'N/A':
        print(f"{k:<40} {str(r):>15} {str(o):>15}")
    else:
        diff = o - r
        print(f"{k:<40} {r:>15.2f} {o:>15.2f} {diff:>+15.2f}")
