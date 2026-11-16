# Resultado de la demo de punta a punta

Cuadros procesados: 48 · tiempo medio por cuadro (detector + OCR): 31.4 ms

## Eventos emitidos por las cámaras

| Evento | Cámara | Hora | Placa | Lecturas por cuadro | Votadas |
|---|---|---|---|---|---|
| EV-20261015-000001 | AV-01 | 08:42:01 | **VBD-001** | V8D001 VBD001 VBD001 VBD001 VBD001 V8D001 VBD001 VBD001 | 8/8 |
| EV-20261015-000002 | AV-08 | 08:44:01 | **VBD-001** | VBD001 - VBD001 V8D001 - VBD001 VBD001 VBD001 | 6/8 |
| EV-20261015-000003 | AV-01 | 08:43:11 | **D9R-052** | DOR052 DOR052 DOR052 D9R052 D9R052 I9R052 D9R052 DOR052 | 8/8 |
| EV-20261015-000004 | AV-08 | 08:46:31 | **DOR-052** | DOR052 DOR052 I2R052 DOR052 DOR052 DOR052 DOR052 DOR052 | 8/8 |
| EV-20261015-000005 | AV-01 | 08:45:01 | **T3P-298** | TZP298 TSP298 T3P298 T3P298 T3P298 T3P298 T3P298 T3P298 | 8/8 |
| EV-20261015-000006 | AV-12 | 08:46:01 | **T3P-298** | T3P298 T3P298 T3P298 T3P298 T3P298 T3P298 T3P298 T3P298 | 8/8 |

## Decisiones del motor (grafo)

- **INFRACCIÓN VBD-001**: AV-01 → AV-08, 3.0 km en 120 s → 87.1 km/h conservadora (límite 60), exceso +27.1 km/h. Pasa a validación humana.
- Sin infracción DOR-052: 3.0 km en 200 s → 52.9 km/h.
- **ALERTA T3P-298**: AV-01 → AV-12 (6.8 km) en 1.0 min: exigiría 408.0 km/h (máximo plausible 200). Captura físicamente imposible: posible placa clonada o error de lectura.
