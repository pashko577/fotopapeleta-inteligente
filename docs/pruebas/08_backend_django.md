# 08 · Backend Django (API, base de datos, validación y papeletas)

## Objetivo
Llevar el sistema a una aplicación web real: recibir los eventos del worker por HTTP, guardarlos, decidir con el grafo, permitir la validación humana y emitir la papeleta. Todo con permisos por rol y trazabilidad.

## Qué se construyó

| Pieza | Ubicación | Función |
|---|---|---|
| Proyecto | `web/config/` | Django 5.2.18 LTS + Django REST Framework 3.18.3, SQLite, español, zona horaria America/Lima |
| App `camaras` | `web/camaras/` | Modelos `Camara` y `Tramo` (nodos y aristas del grafo, editables desde el admin). `servicios.py` arma el grafo desde la BD y calcula su **versión** (huella del contenido) |
| App `infracciones` | `web/infracciones/` | `Captura`, `Evidencia`, `Infraccion` (ciclo de vida), `AnalisisGrafo` (ruta, tiempos, velocidad y versión del grafo) y `Alerta`. `servicios.py` registra cada evento y decide |
| App `validacion` | `web/validacion/` | `Validacion`, `Papeleta` (numeración correlativa FP-AAAA-NNNNNN) y `SolicitudRevision`. `servicios.py` aplica las reglas de la decisión humana |
| Decisión | `grafo/decision.py` | `evaluar_evento()`: la **misma función** la usan la API y la demo |

**Ciclo de una infracción en el sistema:**
1. El worker envía `POST /api/eventos/` con la placa, la cámara y la hora.
2. Se guarda la **captura** y se buscan capturas recientes (±3 h) de la misma placa o de una parecida.
3. `grafo.evaluar_evento()` decide: infracción (→ estado **En validación**, con su análisis), tramo sin infracción, o **alerta** de captura imposible.
4. Un validador aprueba (opcionalmente corrigiendo la placa) → se emite la **papeleta**; o rechaza con un motivo obligatorio.

## API

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| POST | `/api/eventos/` | worker (token) | Registra un evento; responde con la captura, las infracciones, los tramos sin infracción y las alertas. Un evento repetido (mismo `evento_id`) no se procesa dos veces |
| GET | `/api/grafo/` | cualquier usuario autenticado | Red de cámaras y versión |
| GET | `/api/infracciones/?estado=&placa=` | validador, administrador | Listado con capturas, evidencias, análisis y papeleta |
| POST | `/api/infracciones/{id}/validar/` | validador, administrador | `{"decision": "aprobar"\|"rechazar", "motivo": "", "placa_corregida": ""}` |
| GET | `/api/capturas/` | validador, administrador | Capturas con evidencias |
| GET / PATCH | `/api/alertas/` | validador, administrador | Alertas; se marcan como revisadas |
| — | `/admin/` | administrador | Panel de administración completo |

**Roles** (`python manage.py crear_roles`): `worker` (solo reportar capturas), `validador` (ver y validar), `administrador` (todo). El worker se autentica con **token**; las personas, con sesión.

## Comandos de gestión

| Comando | Qué hace |
|---|---|
| `python manage.py importar_red [ruta]` | Carga cámaras y tramos desde `data/grafo_camaras.json` (validando la red) |
| `python manage.py crear_roles --worker USUARIO` | Crea los grupos con sus permisos y un usuario worker con su token |
| `python manage.py importar_eventos ../demo/salida/eventos.json` | Pasa los eventos de la demo **por el mismo flujo de la API** y adjunta sus imágenes de evidencia |

## Pruebas automáticas: 16/16 aprobadas (`web/infracciones/tests.py`)

| Grupo | Pruebas |
|---|---|
| Decisión | Infracción de velocidad con su análisis (87.1 km/h, +27.1); sin infracción con vínculo "a verificar"; alerta por captura imposible; **regresión: auto a 94.7 km/h es infracción**; evento repetido no duplica; hora sin zona se toma como hora de Lima; cámara inexistente rechazada |
| Permisos | Sin token → 401; usuario sin rol no reporta ni valida → 403; **el worker no puede ver infracciones ni alertas** → 403 |
| Validación | Aprobar con placa corregida (VBD001 → V8D001) emite la papeleta con la placa corregida; rechazar exige motivo; no se valida dos veces; numeración correlativa |
| Consultas | Filtro por estado y placa; red de cámaras |

## Prueba en vivo

Se levantó el servidor y se enviaron eventos por HTTP, igual que lo hará el worker.

| Caso | Resultado |
|---|---|
| Carga de los 6 eventos de la demo (`importar_eventos`) | 1 infracción, 1 tramo sin infracción y 1 alerta, igual que la demo; 12 imágenes de evidencia guardadas |
| ABC-123: AV-01 09:00:00 → AV-08 09:01:50 (3 km en 110 s) | **Infracción**: 94.7 km/h conservadora, +34.7 km/h |
| XYZ-789: 3 km en 45 s | **Alerta**: exigiría 240 km/h |
| Mismo evento enviado dos veces | HTTP 200, sin duplicar |
| Token del worker → `/api/infracciones/` | HTTP 403 |
| Sin token → `/api/eventos/` | HTTP 401 |

## Error encontrado en la prueba en vivo

**Síntoma:** ABC-123 a **94.7 km/h en zona de 60** no generó infracción, sino una **alerta de placa clonada**.

**Causa:** el filtro que separa capturas posibles de imposibles aceptaba una captura solo si el tiempo transcurrido era **al menos la mitad del tiempo típico** del tramo. En AV-01 → AV-08 el tiempo típico es 4 min (45 km/h), así que todo lo que superaba **90 km/h** se consideraba imposible. Justo los infractores más graves nunca se multaban.

**Por qué no lo detectaron las pruebas:** los casos usados (87.1 km/h y 1 min frente a 9 min) estaban lejos del umbral.

**Corrección:** "imposible" pasa a significar que, por la ruta más corta, haría falta ir a más de **200 km/h** (parámetro `VELOCIDAD_MAX_PLAUSIBLE_KMH`).

| Velocidad necesaria por la ruta más corta | Decisión |
|---|---|
| Hasta límite + tolerancia (65 km/h) | Sin infracción |
| Entre 65 y 200 km/h | **Infracción** → validación humana |
| Más de 200 km/h | **Alerta**: posible placa clonada o error de lectura |

Se agregaron pruebas de regresión con el caso exacto (94.7 km/h → infracción) y con uno por encima del umbral (216 km/h → alerta). Las decisiones de la demo (07) no cambian. Lección: **probar con valores cerca de los umbrales**, no solo con casos cómodos.

## Otras observaciones
- El puerto 8765 estaba ocupado por otro programa de la PC, que respondía `{"ok":false,"message":"No autorizado"}`. Se usó el puerto 8000. No se tocó el otro programa.
- En Django 5.2, `manage.py shell` imprime una línea informativa antes de la salida; para obtener solo el token hay que usar `-v 0`.
- La clave secreta y `DEBUG` se leen de variables de entorno (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`); el valor incluido solo sirve para desarrollo local.

## Pendiente
- ~~Pantallas web (portal ciudadano y panel) a partir del prototipo de pencil.dev.~~ Hecho: ver [09](09_pantallas_web.md).
- Conectar el worker (`percepcion/pipeline.py`) a la API (pendiente S1).
- Subida de las imágenes de evidencia desde el worker (hoy solo se envían los nombres; `importar_eventos` adjunta los archivos).

## Cómo reproducir
```bash
cd web
python manage.py migrate
python manage.py importar_red
python manage.py crear_roles --worker worker-demo      # muestra el token
python manage.py createsuperuser                        # usuario para /admin/
python manage.py importar_eventos ../demo/salida/eventos.json
python manage.py test                                   # 16 pruebas
python manage.py runserver 8000
```
