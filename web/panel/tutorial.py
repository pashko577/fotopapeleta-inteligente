"""Recorridos guiados del panel (driver.js). Un recorrido por pantalla; cada paso apunta a un elemento
con el atributo data-tour="…". Los pasos con permiso solo se muestran a quien puede usar esa función.

Paso: (data-tour, título, texto, permiso o None, lado de la burbuja)
"""
BIENVENIDA = ("", "Bienvenido a FotoPapeleta",
              "Te mostramos para qué sirve cada parte en menos de un minuto. Puedes salir con Esc y volver a verlo "
              "desde el botón «?» de la barra superior.", None, "over")

COMUNES = [
    ("menu", "Menú principal", "Operación (el día a día), Red (cámaras y algoritmos), Análisis y Sistema. "
     "El número en Validación son las infracciones que esperan una decisión humana.", None, "right"),
    ("buscar", "Búsqueda rápida", "Escribe una placa (ABC-123), un ID (INF-000123), una papeleta (FP-…) o una cámara (AV-01). "
     "Atajo: Ctrl K.", None, "bottom"),
    ("worker", "Estado del worker", "El programa que mira las cámaras y lee las placas. Verde: envió eventos en los "
     "últimos 5 minutos.", None, "bottom"),
    ("notificaciones", "Notificaciones", "Alertas de captura imposible: la misma placa en dos cámaras en un tiempo que "
     "exigiría más de 200 km/h. Puede ser una placa clonada o un error de lectura.", None, "bottom"),
    ("ayuda", "Volver a ver esta guía", "Cada pantalla tiene su propia guía. Ábrela aquí cuando quieras.", None, "bottom"),
]

PASOS = {
    "resumen": [
        ("kpis", "Indicadores del día", "Infracciones detectadas, pendientes de validar, tasa de aprobación de los "
         "validadores y cámaras activas.", None, "bottom"),
        ("grafico", "Infracciones por hora", "Cuándo se concentran las infracciones. Cada color es un tipo de infracción.", None, "top"),
        ("cola", "Cola de validación", "Las infracciones más antiguas esperando una decisión. Ninguna papeleta se emite "
         "sin que una persona la apruebe.", None, "left"),
        ("camaras", "Estado de cámaras", "Cada cámara es un nodo del grafo. Aquí ves cuándo envió su última captura.", None, "left"),
    ],
    "validacion": [
        ("cola", "Cola", "Elige una infracción. Las marcadas «Escalada» esperan la opinión de un administrador.", None, "right"),
        ("pestanas", "Una pestaña por cámara", "La misma placa vista en dos cámaras. Revisa que sea el mismo vehículo en "
         "ambas imágenes.", None, "bottom"),
        ("evidencia", "Evidencia", "La imagen de la cámara con la hora, la confianza del OCR y cuántas lecturas coincidieron. "
         "Debajo están las miniaturas y el recorte de la placa.", None, "right"),
        ("placa", "Placa detectada", "Si el OCR confundió un carácter (8 por B, 0 por D), corrígela antes de aprobar: la "
         "papeleta sale con la placa corregida.", "validacion.add_validacion", "left"),
        ("analisis", "Análisis del grafo", "A* calcula la ruta más corta entre las cámaras. Con esa distancia y el tiempo más "
         "un margen de error de reloj se obtiene la velocidad más baja posible: si aun así supera el límite + 5 km/h, "
         "hay infracción.", None, "left"),
        ("decision", "Tu decisión", "Aprobar emite la papeleta. Rechazar pide un motivo. Escalar la deja en la cola para un "
         "administrador. Atajos: A, R y E.", "validacion.add_validacion", "top"),
    ],
    "infracciones": [
        ("filtros", "Filtros", "Filtra por placa, tipo, estado, cámara o fechas. La tabla se actualiza sin recargar la página.", None, "bottom"),
        ("tabla", "Todas las infracciones", "Haz clic en el ID para ver el detalle y su registro de auditoría. Marca filas "
         "para exportarlas.", None, "top"),
        ("exportar", "Exportar", "Descarga lo filtrado en CSV (se abre en Excel).", None, "left"),
    ],
    "papeletas": [
        ("pestanas", "Estados de la papeleta", "Emitida, En revisión (el ciudadano pidió revisarla) o Anulada.", None, "bottom"),
        ("tabla", "Papeletas emitidas", "Desde el menú «⋮» de cada fila: ver el detalle, descargar el PDF, copiar el enlace "
         "público o anularla con un motivo (solo administradores).", None, "top"),
    ],
    "camaras": [
        ("mapa", "Red de cámaras (grafo)", "Cada círculo es una cámara y cada línea un tramo de calle con su distancia. "
         "Haz clic en una cámara para ver su detalle.", None, "right"),
        ("detalle", "Detalle", "Capturas, última imagen y tramos conectados de la cámara elegida.", None, "left"),
        ("agregar", "Agregar cámara", "Una cámara nueva entra al grafo con su primer tramo. El sistema verifica que la "
         "distancia del tramo no sea menor que la línea recta, para que A* siga siendo exacto.", "camaras.add_camara", "left"),
    ],
    "captura": [
        ("worker", "Worker de percepción", "Versión de los modelos y cuántos eventos llegaron hoy.", None, "bottom"),
        ("tarjetas", "Cámaras", "La última imagen de cada cámara con la placa leída.", None, "right"),
        ("lecturas", "Lecturas recientes", "Se actualiza sola cada 5 segundos.", None, "left"),
    ],
    "subir": [
        ("formulario", "Subir una foto o un video", "Elige la cámara, la hora y el archivo. Pasa por el mismo detector y OCR "
         "que usa el worker. En un video se leen varios cuadros y se vota la placa, por eso acierta más.", None, "right"),
        ("manual", "Si el OCR no la lee", "Puedes escribir la placa a mano: quedará marcada como escrita por una persona.", None, "right"),
        ("ejemplo", "Cómo probar una infracción", "Sube el mismo auto en dos cámaras con dos minutos de diferencia.", None, "left"),
    ],
    "transito": [
        ("mapa", "Cámaras públicas reales", "Cámaras de tránsito de Lima (señal de la Municipalidad, vía Claro) en su ubicación "
         "real. El color indica el tráfico comparado con lo normal en esa cámara. No leen placas: solo cuentan vehículos.", None, "right"),
        ("ruta", "Ruta más rápida ahora", "A* busca la ruta con los tiempos actuales: cada tramo parte de su tiempo a flujo "
         "libre y se alarga si sus cámaras ven más tráfico de lo normal.", None, "left"),
        ("tabla", "Mediciones", "YOLOv8 cuenta autos, motos, buses y camiones con seguimiento entre cuadros. Haz clic en una "
         "cámara para ver el video en vivo y medir ahora.", None, "top"),
    ],
    "laboratorio": [
        ("parametros", "Parámetros", "BFS busca cámaras cercanas (vecindario de k saltos), DFS enumera rutas y A* encuentra "
         "la más corta. Prueba A* con y sin heurística.", None, "right"),
        ("resultado", "Resultado en el grafo", "Origen en azul, destino en verde, ruta en ámbar. El número sobre cada nodo es "
         "el orden en que el algoritmo lo exploró.", None, "left"),
        ("velocidad", "Velocidad por tramo", "La misma fórmula que usa el sistema para decidir: distancia mínima entre el "
         "tiempo observado más el margen de reloj.", None, "top"),
    ],
    "reportes": [
        ("periodo", "Periodo", "Hoy, 7 días o el mes. «Exportar PDF» imprime la página.", None, "bottom"),
        ("kpis", "Indicadores", "Volumen, tasa de aprobación, tiempo que tarda una persona en decidir y revisiones pedidas.", None, "bottom"),
        ("calidad", "Calidad de los modelos", "Resultados de la evaluación del detector y del OCR (de las pruebas, no de la "
         "operación del día).", None, "left"),
    ],
    "configuracion": [
        ("preferencias", "Tus preferencias", "Tema, densidad, refresco de la cola y atajos. Se guardan en este navegador.", None, "right"),
        ("parametros", "Parámetros del sistema", "Tolerancia, velocidad máxima plausible, error de reloj y profundidad de BFS. "
         "Solo un administrador los cambia; se aplican a los eventos nuevos.", None, "left"),
    ],
    "usuarios": [
        ("usuarios", "Usuarios", "Cada persona tiene un rol: administrador, validador o worker (el programa de las cámaras).", None, "right"),
        ("permisos", "Permisos por rol", "Qué puede hacer cada rol, leído de los permisos reales del sistema.", None, "left"),
    ],
}


def pasos(pantalla, usuario, primera_vez_en_el_panel=False):
    """Pasos de una pantalla para este usuario (sin los que no puede usar)."""
    lista = list(PASOS.get(pantalla, []))
    if primera_vez_en_el_panel:
        lista = [BIENVENIDA] + lista + COMUNES
    return [{"tour": t, "titulo": ti, "texto": tx, "lado": lado}
            for t, ti, tx, permiso, lado in lista if not permiso or usuario.has_perm(permiso)]
