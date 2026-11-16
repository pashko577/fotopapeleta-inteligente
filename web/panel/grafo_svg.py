"""GraphCanvas (sección 8.4): la red de cámaras como SVG generado en el servidor.

Las coordenadas salen de x_km/y_km (red esquemática de evaluación) o de lat/lon proyectadas (red real).
En el mapa real de Cámaras se usa Leaflet; este SVG queda para el laboratorio y las vistas compactas.
"""
from camaras.models import Camara, Tramo


def posiciones_km(camaras):
    """{codigo: (x_km, y_km)}: las coordenadas esquemáticas si existen; si no, lat/lon proyectadas a km (este, norte)."""
    import math
    con_latlon = [c for c in camaras if c.lat is not None and c.lon is not None]
    lat0 = sum(c.lat for c in con_latlon) / len(con_latlon) if con_latlon else 0
    lon0 = sum(c.lon for c in con_latlon) / len(con_latlon) if con_latlon else 0
    pos = {}
    for c in camaras:
        if c.x_km is not None and c.y_km is not None:
            pos[c.codigo] = (c.x_km, c.y_km)
        elif c.lat is not None and c.lon is not None:
            pos[c.codigo] = ((c.lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (c.lat - lat0) * 110.57)
        else:
            pos[c.codigo] = (0.0, 0.0)
    return pos


def _repartir(pos):
    """Para el esquema de una red real: mitad posición real, mitad orden (oeste-este, sur-norte).

    En la ciudad real unas cámaras quedan a 600 m y otras a 10 km; con el orden repartido el dibujo se lee y conserva
    la orientación. Es solo para el dibujo: las distancias de las etiquetas siguen siendo las reales.
    """
    def eje(i):
        valores = sorted({p[i] for p in pos.values()})
        lo, hi = valores[0], valores[-1]
        rango = (hi - lo) or 1
        return {v: 0.5 * (v - lo) / rango + 0.5 * (valores.index(v) / max(len(valores) - 1, 1)) for v in valores}
    ex, ey = eje(0), eje(1)
    return {c: (ex[x], ey[y]) for c, (x, y) in pos.items()}


def lienzo(ancho=900, alto=360, ruta=None, visitados=None, orden=None, origen=None, destino=None,
           etiquetas="km", seleccion=None, margen=60, estados=None):
    """Datos listos para componentes/grafo.html.

    ruta: lista de códigos (se resalta en ámbar) · visitados: códigos explorados · orden: {codigo: n}
    etiquetas: "km" (3.0 km · 4 min), "corta" (solo km) o None · estados: {codigo: "online"|"offline"}
    """
    camaras = list(Camara.objects.filter(activa=True))
    tramos = list(Tramo.objects.filter(origen__activa=True, destino__activa=True))
    pos = posiciones_km(camaras)
    if pos and any(c.x_km is None for c in camaras):
        pos = _repartir(pos)
    if not pos:
        return {"ancho": ancho, "alto": alto, "nodos": [], "aristas": []}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    ex, ey = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1

    def px(codigo):
        x, y = pos[codigo]
        return (margen + (x - min(xs)) / ex * (ancho - 2 * margen),
                margen * 0.8 + (max(ys) - y) / ey * (alto - 1.8 * margen))  # y_km crece hacia el norte

    ruta = ruta or []
    en_ruta = {frozenset(p) for p in zip(ruta, ruta[1:])}
    visitados, orden, estados = set(visitados or []), orden or {}, estados or {}
    aristas = []
    for t in tramos:
        (x1, y1), (x2, y2) = px(t.origen_id), px(t.destino_id)
        resaltada = frozenset((t.origen_id, t.destino_id)) in en_ruta
        texto = None
        if etiquetas == "km":
            texto = f"{t.km:.1f} km · {t.minutos:g} min"
        elif etiquetas == "corta":
            texto = f"{t.km:.1f} km"
        aristas.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                        "texto": texto, "ancho_texto": len(texto or "") * 6.4 + 12, "ruta": resaltada,
                        "dirigida": t.dirigida})
    nodos = []
    for c in camaras:
        x, y = px(c.codigo)
        rol = ("origen" if c.codigo == origen else "destino" if c.codigo == destino
               else "visitado" if c.codigo in visitados else "normal")
        nodos.append({"codigo": c.codigo, "nombre": c.nombre, "x": x, "y": y, "rol": rol,
                      "orden": orden.get(c.codigo), "seleccionado": c.codigo == seleccion,
                      "estado": estados.get(c.codigo)})
    return {"ancho": ancho, "alto": alto, "nodos": nodos, "aristas": aristas}
