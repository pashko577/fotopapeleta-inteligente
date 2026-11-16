# FotoPapeleta Inteligente — Especificación de diseño del prototipo (pencil.dev)

**Para:** el equipo que construirá el prototipo en pencil.dev y luego lo pasará a código.
**Documentos relacionados:** `plan_fotopapeleta_inteligente.md` (qué y por qué) · `arquitectura_fotopapeleta_inteligente.md` (cómo está construido).
**Stack de destino del código:** plantillas Django + Tailwind CSS v4 + HTMX + Alpine.js + íconos Lucide (ver sección 14).

> Este documento es la fuente única del diseño. Todo valor (color, tamaño, espaciado, ícono) que aparezca en pencil.dev debe salir de aquí. Si algo no está definido, se agrega primero aquí y después se diseña.

---

## 0. Cómo usar este documento en pencil.dev

Orden de construcción recomendado (de lo general a lo particular):

1. **Variables y temas** (sección 2–6): crear todas las variables con los ejes de tema `mode` y `density`.
2. **Página de componentes** (sección 8): construir cada componente como `reusable: true` en la parte superior del lienzo.
3. **Pantallas** (sección 10–11): debajo de los componentes, una pantalla por frame de primer nivel, creciendo hacia la derecha y hacia abajo. Las pantallas usan **solo instancias (`ref`)** de los componentes.
4. **Estados** (sección 12): cargando, vacío, error y sin permiso para cada pantalla con datos.
5. **Revisión** con la lista de verificación (sección 16).

**Reglas que no se negocian:**
- **Prohibido usar emojis.** Toda iconografía se hace con nodos `icon` de la biblioteca **Lucide** (sección 7).
- **Ningún color, tamaño o espaciado “a mano”.** Siempre se referencia una variable (`$color-primary`, `$space-4`, …).
- **Nada de logos dibujados con trazos.** La marca es tipográfica más un ícono (sección 9.1).
- **Todo texto en español**, con los datos de ejemplo de la sección 13.

### 0.1 Nomenclatura en pencil.dev

| Elemento | Convención | Ejemplo |
|---|---|---|
| Variables | `categoria-nombre[-variante]` en minúsculas con guiones | `color-primary-hover`, `space-4`, `radius-md` |
| Componentes | `Categoría/Nombre/Variante` (en el campo `name`) | `Button/Primary/md`, `Badge/Estado/Aprobada` |
| Pantallas | `Área · Código · Nombre · Dispositivo` | `Panel · A4 · Validación · Desktop` |
| Capas internas | Nombre funcional, no visual | `Header`, `Acciones`, `ListaCola` (no `Frame 12`) |

---

## 1. Principios de diseño

| Principio | Qué significa en las pantallas |
|---|---|
| **Confianza institucional** | Paleta sobria (azul institucional + neutros). Sin decoración gratuita, sin degradados llamativos. |
| **La evidencia manda** | En validación y detalle, la imagen de evidencia es la región dominante. |
| **Estado siempre visible** | Toda infracción muestra su estado con color **y** texto **y** ícono (nunca solo color). |
| **Una acción primaria por pantalla** | Consulta → “Consultar”. Validación → “Aprobar”. El resto es secundario. |
| **Datos legibles** | Placas, horas, IDs y cifras en tipografía monoespaciada con dígitos tabulares. |
| **Accesible desde el inicio** | Contraste AA, foco visible, objetivos táctiles de 44 px, etiquetas en íconos. |

---

## 2. Temas (ejes en pencil.dev)

```json
"themes": {
  "mode":    ["light", "dark"],
  "density": ["comfortable", "compact"]
}
```

- `mode` controla los colores (sección 3).
- `density` controla altura de controles, filas de tabla y paddings (sección 5.3). Lo usa el **toggle de preferencias** “Densidad”.
- Cada pantalla de primer nivel declara su tema, por ejemplo `theme: { "mode": "dark" }`, para mostrar ambas versiones lado a lado.

---

## 3. Color

Todos son variables de tipo `color` con valor por tema `mode`.

### 3.1 Superficies y texto

| Variable | Light | Dark | Uso |
|---|---|---|---|
| `color-bg` | `#F6F7F9` | `#0B1120` | Fondo general de la aplicación |
| `color-surface` | `#FFFFFF` | `#111827` | Cards, tablas, sidebar, topbar, modales |
| `color-surface-muted` | `#F1F3F6` | `#1A2333` | Hover de filas, inputs deshabilitados, zonas secundarias |
| `color-surface-sunken` | `#E9EDF2` | `#0E1626` | Fondo del lienzo del mapa/grafo, pozos de imagen |
| `color-border` | `#E2E6EC` | `#263042` | Bordes de cards, divisores, tablas |
| `color-border-strong` | `#CBD2DB` | `#364152` | Bordes de inputs, separadores con énfasis |
| `color-text` | `#0F172A` | `#F1F5F9` | Texto principal |
| `color-text-secondary` | `#475569` | `#CBD5E1` | Texto de apoyo, etiquetas |
| `color-text-muted` | `#64748B` | `#94A3B8` | Placeholders, metadatos, texto deshabilitado |
| `color-text-inverse` | `#FFFFFF` | `#0F172A` | Texto sobre fondos oscuros/claros invertidos (tooltip) |
| `color-overlay` | `#0F172A99` | `#00000099` | Fondo detrás de modales y drawers |

### 3.2 Marca y acción

| Variable | Light | Dark | Uso |
|---|---|---|---|
| `color-primary` | `#1D4ED8` | `#2563EB` | Botón primario, enlaces, ítem activo, foco |
| `color-primary-hover` | `#1E40AF` | `#1D4ED8` | Hover/pressed del primario |
| `color-primary-subtle` | `#EFF4FF` | `#172554` | Fondo de ítem activo en sidebar, fila seleccionada, chip activo |
| `color-primary-text` | `#1E40AF` | `#93C5FD` | Texto primario sobre `primary-subtle`; enlaces en dark |
| `color-on-primary` | `#FFFFFF` | `#FFFFFF` | Texto/ícono sobre `color-primary` |
| `color-accent` | `#F59E0B` | `#FBBF24` | Acento vial (ámbar). **Solo** para resaltar la ruta en el mapa y el indicador “en vivo”. Nunca texto sobre blanco. |
| `color-focus-ring` | `#93B4FF` | `#3B82F6` | Anillo de foco de 2 px |

### 3.3 Estados semánticos

| Variable | Light | Dark | Uso |
|---|---|---|---|
| `color-success` | `#15803D` | `#4ADE80` | Texto/ícono de éxito |
| `color-success-subtle` | `#ECFDF3` | `#052E16` | Fondo de badge/banner de éxito |
| `color-warning` | `#B45309` | `#FBBF24` | Texto/ícono de advertencia |
| `color-warning-subtle` | `#FFFBEB` | `#2A1F05` | Fondo de badge/banner de advertencia |
| `color-danger` | `#B91C1C` | `#F87171` | Texto/ícono de error; botón destructivo (light) |
| `color-danger-solid` | `#DC2626` | `#DC2626` | Fondo del botón destructivo |
| `color-danger-subtle` | `#FEF2F2` | `#3B0A0A` | Fondo de badge/banner de error |
| `color-info` | `#0369A1` | `#38BDF8` | Texto/ícono informativo |
| `color-info-subtle` | `#F0F9FF` | `#082F49` | Fondo de badge/banner informativo |
| `color-neutral-subtle` | `#F1F5F9` | `#1E293B` | Badge neutro |

### 3.4 Estados de la infracción (ciclo de vida)

Cada estado usa **color + ícono + texto**. Se construyen como variantes del componente `Badge/Estado`.

| Estado | Fondo | Texto/ícono | Ícono Lucide |
|---|---|---|---|
| Detectada | `color-neutral-subtle` | `color-text-secondary` | `scan-line` |
| Enriquecida | `color-info-subtle` | `color-info` | `waypoints` |
| En validación | `color-warning-subtle` | `color-warning` | `hourglass` |
| Aprobada | `color-success-subtle` | `color-success` | `circle-check` |
| Rechazada | `color-danger-subtle` | `color-danger` | `circle-x` |
| Emitida | `color-primary-subtle` | `color-primary-text` | `file-check` |
| En revisión | `color-warning-subtle` | `color-warning` | `message-square` |
| Anulada | `color-neutral-subtle` | `color-text-muted` | `ban` |

### 3.5 Tipos de infracción (categóricos para gráficos y etiquetas)

| Variable | Valor (ambos temas) | Tipo | Ícono Lucide |
|---|---|---|---|
| `color-cat-velocidad` | `#2563EB` | Exceso de velocidad | `gauge` |
| `color-cat-semaforo` | `#DC2626` | Semáforo en rojo | `octagon-alert` |
| `color-cat-peatonal` | `#D97706` | Invasión de cruce peatonal | `footprints` |
| `color-cat-celular` | `#7C3AED` | Uso de celular | `smartphone` |
| `color-cat-giro` | `#0891B2` | Giro prohibido | `corner-up-right` |
| `color-cat-contrario` | `#DB2777` | Sentido contrario | `arrow-left-right` |
| `color-cat-senales` | `#4D7C0F` | No respetar señales | `signpost` |

Los colores categóricos se usan en **barras de gráficos, puntos de leyenda y el ícono** de la etiqueta de tipo. El texto de la etiqueta sigue en `color-text`.

### 3.6 Mapa y grafo

| Variable | Light | Dark | Uso |
|---|---|---|---|
| `color-graph-node` | `#FFFFFF` | `#1A2333` | Relleno del nodo cámara |
| `color-graph-node-border` | `#475569` | `#94A3B8` | Borde del nodo cámara |
| `color-graph-edge` | `#CBD2DB` | `#364152` | Arista normal |
| `color-graph-visited` | `#93C5FD` | `#1E3A8A` | Nodo explorado por el algoritmo |
| `color-graph-route` | `#F59E0B` | `#FBBF24` | Ruta resultante (A\*) y aristas de la ruta |
| `color-graph-origin` | `#1D4ED8` | `#3B82F6` | Nodo origen |
| `color-graph-target` | `#15803D` | `#4ADE80` | Nodo destino |
| `color-camera-online` | `#16A34A` | `#4ADE80` | Punto de estado “en línea” |
| `color-camera-offline` | `#DC2626` | `#F87171` | Punto de estado “sin señal” |

---

## 4. Tipografía

### 4.1 Familias

| Variable (`string`) | Valor | Uso |
|---|---|---|
| `font-sans` | `Inter` | Toda la interfaz |
| `font-mono` | `JetBrains Mono` | Placas, IDs, horas, coordenadas, cifras en tablas y KPIs |

Ambas son Google Fonts (disponibles en pencil.dev y en el código).

### 4.2 Escala tipográfica

| Estilo | Familia | Tamaño | Peso | Interlineado (`lineHeight`) | Espaciado | Uso |
|---|---|---|---|---|---|---|
| `display` | sans | 36 | 700 | 1.15 | -0.02 | Título del portal (“Consulta tus papeletas”) |
| `h1` | sans | 28 | 600 | 1.2 | -0.01 | Título de pantalla |
| `h2` | sans | 20 | 600 | 1.3 | 0 | Título de sección / card |
| `h3` | sans | 16 | 600 | 1.4 | 0 | Subtítulo, título de modal |
| `body-lg` | sans | 16 | 400 | 1.5 | 0 | Texto del portal ciudadano (móvil) |
| `body` | sans | 14 | 400 | 1.45 | 0 | Texto por defecto del panel |
| `body-strong` | sans | 14 | 600 | 1.45 | 0 | Valores destacados, etiquetas de botón |
| `small` | sans | 13 | 400 | 1.4 | 0 | Celdas de tabla en densidad compacta, ayudas |
| `caption` | sans | 12 | 500 | 1.35 | 0 | Metadatos, pies de imagen, leyendas |
| `overline` | sans | 11 | 600 | 1.3 | 0.06 | Encabezados de grupo en sidebar y tablas (MAYÚSCULAS) |
| `kpi` | mono | 32 | 600 | 1.1 | -0.01 | Cifra principal de una card KPI |
| `mono` | mono | 14 | 500 | 1.4 | 0 | Placas, IDs, horas en tablas |
| `plate` | mono | 28 | 700 | 1.0 | 0.08 | Placa grande (componente `Placa`) |

Variables numéricas sugeridas: `font-size-display`, `font-size-h1`, … `font-size-overline`, para cambiar la escala en un solo lugar.

**Reglas:**
- Máximo 3 tamaños por card.
- Longitud de línea de párrafos: 60–80 caracteres (ancho máximo 640 px).
- Números en tablas: alineados a la derecha y en `font-mono`.

---

## 5. Espaciado, tamaños y layout

### 5.1 Escala de espaciado (base 4 px)

| Variable | Valor | Uso típico |
|---|---|---|
| `space-1` | 4 | Separación ícono–texto pequeño, dentro de badges |
| `space-2` | 8 | Gap entre ícono y etiqueta de botón; entre chips |
| `space-3` | 12 | Padding de inputs y celdas compactas |
| `space-4` | 16 | Padding de cards compactas; gap entre campos de formulario; margen lateral móvil |
| `space-5` | 20 | Padding de cards estándar |
| `space-6` | 24 | Gap entre cards; padding de secciones; gutter desktop |
| `space-8` | 32 | Margen lateral desktop; separación entre secciones |
| `space-10` | 40 | Separación entre bloques grandes |
| `space-12` | 48 | Padding vertical del hero del portal |
| `space-16` | 64 | Separación de secciones en el portal |

### 5.2 Radios, bordes y elevación

| Variable | Valor | Uso |
|---|---|---|
| `radius-sm` | 4 | Badges, checkboxes, chips de tabla |
| `radius-md` | 8 | Botones, inputs, ítems de sidebar, tooltips |
| `radius-lg` | 12 | Cards, dropdowns, toasts, imágenes de evidencia |
| `radius-xl` | 16 | Modales, drawers, barra flotante |
| `radius-full` | 999 | Switch, avatar, FAB, punto de estado, pills |
| `border-width` | 1 | Bordes por defecto |
| `focus-width` | 2 | Anillo de foco (con separación de 2 px) |

| Elevación | Efecto (`shadow` outer) | Uso |
|---|---|---|
| `elev-0` | ninguno, solo borde `color-border` | Cards, tablas (la interfaz es plana por defecto) |
| `elev-1` | y 1, blur 2, `#0F172A14` | Topbar fija al hacer scroll |
| `elev-2` | y 4, blur 12, `#0F172A1F` | Dropdowns, popovers, tooltips |
| `elev-3` | y 8, blur 24, `#0F172A29` | Barra flotante, FAB, toasts |
| `elev-4` | y 16, blur 48, `#0F172A3D` | Modales y drawers |

En `dark` las sombras casi no se ven: se compensan con un borde `color-border` en todo elemento elevado.

### 5.3 Tamaños de control y táctiles (dependen de `density`)

| Variable | comfortable | compact | Uso |
|---|---|---|---|
| `control-h-sm` | 32 | 28 | Botones/inputs pequeños (filtros de tabla) |
| `control-h-md` | 40 | 36 | Botones e inputs por defecto |
| `control-h-lg` | 48 | 44 | Botón “Consultar” del portal, acciones de validación |
| `table-row-h` | 52 | 40 | Altura de fila de tabla |
| `table-head-h` | 44 | 36 | Altura de encabezado de tabla |
| `card-padding` | 20 | 16 | Padding interno de cards |

**Objetivos táctiles (no dependen de la densidad):**
- Mínimo **44 × 44 px** en todo elemento interactivo de pantallas **móvil y tablet**. Si el ícono es de 20 px, su área táctil (frame contenedor) sigue siendo de 44 px.
- Separación mínima de **8 px** entre objetivos táctiles contiguos.
- En móvil, los botones primarios usan `control-h-lg` (48 px) y ocupan todo el ancho.

### 5.4 Tamaños de íconos

| Variable | Valor | Uso |
|---|---|---|
| `icon-xs` | 14 | Dentro de badges y chips |
| `icon-sm` | 16 | Botones sm/md, celdas de tabla, inputs |
| `icon-md` | 20 | Sidebar, topbar, botones lg |
| `icon-lg` | 24 | Encabezados de card, FAB, navegación inferior móvil |
| `icon-xl` | 40 | Estados vacíos y de error |

Grosor de trazo: el valor por defecto de Lucide (2). No mezclar grosores en una misma pantalla.

> **Limitación de pencil.dev (comprobada en `prot.pen`):** los nodos `icon` y el ancho/alto de los frames **no aceptan variables numéricas**; si se usan, el tamaño se pierde. En pencil.dev se escriben los valores en número (16, 20, 40…) y las variables `icon-*`, `control-h-*` y `table-row-h` se aplican recién en el código (CSS). Por eso el eje `density` solo cambia paddings en el diseño; la altura compacta se implementa con `[data-density="compact"]`. Las variables de color, tipografía, padding, gap y radio sí funcionan.

### 5.5 Dispositivos, rejilla y estructura

| Dispositivo | Frame | Columnas | Gutter | Margen lateral |
|---|---|---|---|---|
| Móvil | 390 × 844 | 4 | 16 | 16 |
| Tablet | 834 × 1194 | 8 | 16 | 24 |
| Desktop | 1440 × 900 (alto según contenido) | 12 | 24 | 32 |

| Elemento estructural | Medida |
|---|---|
| Sidebar expandida | 256 px |
| Sidebar colapsada | 72 px (solo íconos + tooltip) |
| Topbar | 64 px |
| Banner de sistema | 44 px (texto en una línea) |
| Ancho máximo de contenido del panel | 1280 px |
| Ancho máximo del portal ciudadano | 960 px |
| Navegación inferior móvil | 64 px + área segura 34 px |

### 5.6 Capas (orden de superposición)

| Capa | Elementos |
|---|---|
| 0 | Contenido |
| 10 | Topbar y encabezados de tabla fijos |
| 20 | Dropdowns, popovers, tooltips |
| 30 | Barra flotante de acciones, FAB, controles flotantes del mapa |
| 40 | Drawers / bottom sheets |
| 50 | Modales |
| 60 | Toasts |

### 5.7 Movimiento (para la implementación)

| Variable | Valor | Uso |
|---|---|---|
| `motion-fast` | 120 ms | Hover, cambio de color, switch |
| `motion-base` | 200 ms | Dropdowns, tooltips, expandir sidebar |
| `motion-slow` | 300 ms | Drawers, modales, toasts |
| Curva | `cubic-bezier(0.2, 0, 0, 1)` | Todas las transiciones |

Respetar `prefers-reduced-motion`: sin desplazamientos, solo fundidos.

---

## 6. Variables de pencil.dev (resumen para copiar)

```json
{
  "themes": { "mode": ["light", "dark"], "density": ["comfortable", "compact"] },
  "variables": {
    "color-primary":   { "type": "color",  "value": [ { "value": "#1D4ED8", "theme": { "mode": "light" } },
                                                       { "value": "#2563EB", "theme": { "mode": "dark" } } ] },
    "color-bg":        { "type": "color",  "value": [ { "value": "#F6F7F9", "theme": { "mode": "light" } },
                                                       { "value": "#0B1120", "theme": { "mode": "dark" } } ] },
    "space-4":         { "type": "number", "value": 16 },
    "radius-md":       { "type": "number", "value": 8 },
    "control-h-md":    { "type": "number", "value": [ { "value": 40, "theme": { "density": "comfortable" } },
                                                       { "value": 36, "theme": { "density": "compact" } } ] },
    "font-sans":       { "type": "string", "value": "Inter" },
    "font-mono":       { "type": "string", "value": "JetBrains Mono" },
    "icon-library":    { "type": "string", "value": "lucide" }
  }
}
```

El resto de variables sigue exactamente este patrón con los valores de las secciones 3 a 5. La variable `icon-library` permite cambiar todos los íconos a `Material Symbols Rounded` en un solo paso si el equipo lo decide (sección 7.3).

---

## 7. Iconografía

### 7.1 Reglas
- **Biblioteca principal: Lucide** (`library: "lucide"` en pencil.dev). Trazo lineal y limpio, coherente con Inter.
- **Prohibido usar emojis** en cualquier texto, botón, estado o mensaje.
- Un ícono **nunca reemplaza** una etiqueta esencial. Excepciones: botones de solo ícono muy conocidos (cerrar, menú, más opciones), que siempre llevan **tooltip** y etiqueta accesible.
- El color del ícono hereda el del texto vecino (`color-text-secondary` por defecto; `color-primary` si está activo).

### 7.2 Mapa de íconos

Los nombres son los de Lucide y Material Symbols. Antes de cerrar el diseño, verificar en lucide.dev y fonts.google.com/icons que cada ícono exista en la versión instalada.

| Concepto | Lucide (pencil / código) | `react-icons` | Material Symbols (Angular Material) |
|---|---|---|---|
| Resumen / dashboard | `layout-dashboard` | `LuLayoutDashboard` | `dashboard` |
| Cámaras | `cctv` | `LuCctv` | `videocam` |
| Infracciones | `triangle-alert` | `LuTriangleAlert` | `warning` |
| Validación | `shield-check` | `LuShieldCheck` | `verified_user` |
| Papeletas | `file-text` | `LuFileText` | `description` |
| Laboratorio del grafo | `waypoints` | `LuWaypoints` | `hub` |
| Mapa | `map` | `LuMap` | `map` |
| Reportes | `chart-column` | `LuChartColumn` | `bar_chart` |
| Usuarios | `users` | `LuUsers` | `group` |
| Configuración | `settings` | `LuSettings` | `settings` |
| Captura en vivo | `radio` | `LuRadio` | `sensors` |
| Buscar placa | `search` | `LuSearch` | `search` |
| Lectura OCR | `scan-text` | `LuScanText` | `document_scanner` |
| Evidencia (imagen) | `image` | `LuImage` | `image` |
| Evidencia (video) | `video` | `LuVideo` | `videocam` |
| Ruta / trayectoria | `route` | `LuRoute` | `route` |
| Ubicación | `map-pin` | `LuMapPin` | `location_on` |
| Hora | `clock-3` | `LuClock3` | `schedule` |
| Fecha | `calendar` | `LuCalendar` | `calendar_today` |
| Aprobar | `check` | `LuCheck` | `check` |
| Rechazar | `x` | `LuX` | `close` |
| Escalar | `flag` | `LuFlag` | `flag` |
| Editar placa | `pencil` | `LuPencil` | `edit` |
| Descargar | `download` | `LuDownload` | `download` |
| Subir archivo | `upload` | `LuUpload` | `upload` |
| Filtros | `list-filter` | `LuListFilter` | `filter_list` |
| Ordenar | `arrow-up-down` | `LuArrowUpDown` | `swap_vert` |
| Más opciones | `ellipsis-vertical` | `LuEllipsisVertical` | `more_vert` |
| Notificaciones | `bell` | `LuBell` | `notifications` |
| Tema claro | `sun` | `LuSun` | `light_mode` |
| Tema oscuro | `moon` | `LuMoon` | `dark_mode` |
| Tema del sistema | `monitor` | `LuMonitor` | `desktop_windows` |
| Menú (móvil) | `menu` | `LuMenu` | `menu` |
| Colapsar sidebar | `panel-left-close` | `LuPanelLeftClose` | `left_panel_close` |
| Expandir sidebar | `panel-left-open` | `LuPanelLeftOpen` | `left_panel_open` |
| Usuario | `user` | `LuUser` | `person` |
| Cerrar sesión | `log-out` | `LuLogOut` | `logout` |
| Ayuda | `circle-question-mark` | `LuCircleHelp` | `help` |
| Información | `info` | `LuInfo` | `info` |
| Éxito | `circle-check` | `LuCircleCheck` | `check_circle` |
| Error | `circle-x` | `LuCircleX` | `cancel` |
| Advertencia | `triangle-alert` | `LuTriangleAlert` | `warning` |
| Privacidad / difuminar | `eye-off` | `LuEyeOff` | `visibility_off` |
| Conexión | `wifi` / `wifi-off` | `LuWifi` / `LuWifiOff` | `wifi` / `wifi_off` |
| Actualizar | `refresh-cw` | `LuRefreshCw` | `refresh` |
| Zoom | `zoom-in` / `zoom-out` | `LuZoomIn` / `LuZoomOut` | `zoom_in` / `zoom_out` |
| Capas del mapa | `layers` | `LuLayers` | `layers` |
| Reproducir / pausar | `play` / `pause` | `LuPlay` / `LuPause` | `play_arrow` / `pause` |
| Copiar | `copy` | `LuCopy` | `content_copy` |
| Abrir en nueva pestaña | `external-link` | `LuExternalLink` | `open_in_new` |
| Navegación | `chevron-right` / `chevron-down` | `LuChevronRight` / `LuChevronDown` | `chevron_right` / `expand_more` |
| Agregar | `plus` | `LuPlus` | `add` |
| Eliminar | `trash-2` | `LuTrash2` | `delete` |
| Atajos de teclado | `keyboard` | `LuKeyboard` | `keyboard` |
| Velocidad | `gauge` | `LuGauge` | `speed` |
| Semáforo en rojo | `octagon-alert` | `LuOctagonAlert` | `traffic` |
| Cruce peatonal | `footprints` | `LuFootprints` | `directions_walk` |
| Uso de celular | `smartphone` | `LuSmartphone` | `smartphone` |
| Giro prohibido | `corner-up-right` | `LuCornerUpRight` | `turn_right` |
| Sentido contrario | `arrow-left-right` | `LuArrowLeftRight` | `swap_horiz` |
| Señales | `signpost` | `LuSignpost` | `signpost` |

### 7.3 Por qué Lucide y no Material Symbols
- Lucide está disponible **en todos los destinos posibles**: pencil.dev, HTML/Django (paquete `lucide` por CDN), React (`lucide-react` o `react-icons/lu`) y Angular (`lucide-angular`). Si el frontend cambia, los íconos no cambian.
- Material Symbols arrastra el estilo visual de Google (Angular Material). Es válido, pero obliga a seguir su lenguaje de diseño. Queda como **alternativa** gracias a la columna de equivalencias.

---

## 8. Componentes

Cada componente se crea como `reusable: true`, con todas sus variantes y estados visibles en la página de componentes. Estados de interacción a dibujar en **todos** los controles: `default`, `hover`, `focus` (anillo `color-focus-ring` de 2 px), `pressed`, `disabled` y, cuando aplique, `loading` y `error`.

### 8.1 Acciones

**Button**

| Variante | Fondo | Texto/ícono | Borde | Uso |
|---|---|---|---|---|
| `primary` | `color-primary` | `color-on-primary` | — | Una por pantalla/sección |
| `secondary` | `color-surface` | `color-text` | `color-border-strong` | Acciones alternativas |
| `ghost` | transparente | `color-text-secondary` | — | Acciones terciarias, barras de herramientas |
| `danger` | `color-danger-solid` | `#FFFFFF` | — | Rechazar, eliminar, anular |
| `success` | `color-success` (light) | `#FFFFFF` | — | Solo “Aprobar” en validación |
| `link` | transparente | `color-primary-text` | — | Enlaces dentro de texto |

- Tamaños `sm` / `md` / `lg` → alto `control-h-sm/md/lg`; padding horizontal 12 / 16 / 20; `radius-md`; gap `space-2`.
- Ícono opcional a la izquierda (o a la derecha para “siguiente”). Estado `loading`: el ícono se reemplaza por `loader-circle`.
- **IconButton**: cuadrado del alto del control, ícono centrado, tooltip obligatorio. En móvil, área mínima de 44 × 44.

**FAB (botón flotante)** — solo en móvil.
- Círculo de 56 px, `color-primary`, ícono `icon-lg`, `elev-3`, a 16 px del borde derecho y 16 px por encima de la navegación inferior.
- Variante extendida (pill) con texto: “Consultar placa” en el portal; “Validar siguiente” en el panel móvil.

**Barra flotante de acciones**
- Aparece al seleccionar filas en una tabla: “3 seleccionadas · Enviar a validación · Exportar · Descartar · [x]”.
- Centrada abajo, a 24 px del borde, `color-surface`, `elev-3`, `radius-xl`, padding `space-3`/`space-4`.

**Barra de decisión (validación)**
- Fija abajo en la columna central de la pantalla de validación: `[Rechazar  R]` `[Escalar  E]` `[Aprobar  A]`.
- Muestra el **atajo de teclado** dentro de cada botón como una tecla (`Kbd`: `font-mono` 12, `color-surface-muted`, `radius-sm`).

### 8.2 Formularios

| Componente | Especificación |
|---|---|
| **Input** | Alto `control-h-md`, `radius-md`, borde `color-border-strong`, padding `space-3`. Etiqueta arriba (`caption`, `color-text-secondary`), texto de ayuda abajo. Ícono opcional izquierda. Estado `error`: borde `color-danger` + mensaje con ícono `circle-x`. |
| **PlacaInput** | Input grande del portal: alto 56, `font-mono` 24, MAYÚSCULAS, máscara `ABC-123`, ícono `search`. Botón “Consultar” integrado a la derecha. Ayuda: “Formato: ABC-123”. |
| **Select** | Igual que Input + `chevron-down`. Abre un `Dropdown`. |
| **DateRange** | Dos inputs con ícono `calendar` + popover de calendario. |
| **Checkbox** | 18 × 18 px, `radius-sm`; marcado: `color-primary` + `check` blanco. Estado indeterminado (selección parcial en tablas). |
| **Radio** | 18 × 18 px, círculo; marcado con punto interno de 8 px. |
| **Switch (toggle)** | Pista 40 × 24 px, `radius-full`. Apagado: pista `color-border-strong`, perilla blanca. Encendido: pista `color-primary`. Perilla de 20 px con `elev-1`. Siempre acompañado de etiqueta a la izquierda y descripción opcional. En móvil, la fila completa es el área táctil (44 px de alto). |
| **SegmentedControl** | Grupo de 2–4 opciones, alto `control-h-md`, fondo `color-surface-muted`, opción activa en `color-surface` con `elev-1`. Usos: tema (Claro / Oscuro / Sistema), algoritmo (BFS / DFS / A\*), peso (km / min). |
| **Slider** | Para umbrales (tolerancia km/h, confianza mínima). Muestra el valor en `font-mono` a la derecha. |
| **Chip de filtro** | Alto 32, `radius-full`, borde `color-border`; activo: `color-primary-subtle` + `color-primary-text` + `x` para quitar. |

### 8.3 Navegación

**Sidebar (panel)**
- Ancho 256 (expandida) / 72 (colapsada), fondo `color-surface`, borde derecho `color-border`.
- Arriba: marca (sección 9.1). Abajo: tarjeta de usuario + botón colapsar.
- Grupos con encabezado `overline` en `color-text-muted`:
  - **OPERACIÓN**: Resumen, Validación (con contador), Infracciones, Papeletas.
  - **RED**: Cámaras, Captura en vivo, Laboratorio del grafo.
  - **ANÁLISIS**: Reportes.
  - **SISTEMA**: Usuarios, Configuración.
- **SidebarItem**: alto 40, `radius-md`, padding horizontal `space-3`, ícono `icon-md` + etiqueta `body` + contador opcional (`Badge/Count`). Activo: fondo `color-primary-subtle`, texto e ícono `color-primary-text`, barra de 3 px a la izquierda en `color-primary`. Colapsada: solo ícono centrado con tooltip a la derecha.
- En tablet y móvil la sidebar se convierte en **drawer** que se abre desde `menu`.

**Topbar (panel)**
- Alto 64, `color-surface`, borde inferior `color-border`.
- Izquierda: breadcrumb (`Panel / Validación / INF-000123`). Centro-derecha: búsqueda global (“Buscar placa, cámara o ID”, atajo `Ctrl K`). Derecha: indicador de worker (`radio` + “Worker en línea”), notificaciones (`bell` con punto), conmutador de tema (`sun`/`moon`), avatar con menú.

**Header del portal ciudadano**
- Alto 64, marca a la izquierda, enlaces “Consultar” · “Cómo funciona” · “Ayuda”, conmutador de tema a la derecha. En móvil: marca + `menu`.

**Navegación inferior (móvil del portal)**
- 3 destinos: Consultar (`search`) · Mis consultas (`history`) · Ayuda (`circle-question-mark`). Ícono `icon-lg` + etiqueta `caption`. Activo en `color-primary`.

**Otros:** `Tabs` (subrayado de 2 px en `color-primary`), `Breadcrumb` (separador `chevron-right` 14 px), `Pagination` (“1–20 de 248”, botones anterior/siguiente, selector de filas por página).

### 8.4 Contenedores y datos

**Card**
- `color-surface`, borde `color-border`, `radius-lg`, padding `card-padding`, `elev-0`.
- Encabezado opcional: título `h2` + acción secundaria a la derecha (`ghost` o `ellipsis-vertical`).
- Usar cards solo cuando agrupan algo con sentido propio; no envolver cada elemento en una card.

**KpiCard**
- Etiqueta (`caption`, `color-text-secondary`) + ícono en esquina, cifra (`kpi`), variación (“+12 % vs. ayer” con `trending-up` / `trending-down` en `color-success` / `color-danger`).
- KPIs del resumen: Infracciones hoy · Pendientes de validación · Tasa de aprobación · Cámaras en línea (8/10).

**Table**
- Encabezado alto `table-head-h`, fondo `color-surface-muted`, texto `overline` en `color-text-secondary`, ícono `arrow-up-down` en columnas ordenables.
- Filas de alto `table-row-h`, divisor inferior `color-border`. Hover: `color-surface-muted`. Seleccionada: `color-primary-subtle`.
- Padding de celda: `space-4` horizontal (`space-3` en compacta).
- Tipos de celda: texto, `mono` (placa, ID, hora), número (derecha), **tipo** (ícono categórico + texto), **estado** (`Badge/Estado`), **confianza** (barra de 48 × 4 px + porcentaje), **acciones** (`ellipsis-vertical`).
- Encabezado fijo al hacer scroll. Primera columna con checkbox para selección múltiple.
- En móvil, la tabla se convierte en **lista de cards** (cada fila = una card con placa, tipo, estado y hora).

**Columnas de la tabla de infracciones:**

| # | Columna | Tipo de celda | Ancho |
|---|---|---|---|
| 1 | (selección) | checkbox | 48 |
| 2 | ID | mono | 140 |
| 3 | Placa | `Placa/sm` | 120 |
| 4 | Tipo | tipo | fill |
| 5 | Cámara | texto + `map-pin` | 160 |
| 6 | Fecha y hora | mono | 170 |
| 7 | Confianza | barra + % | 120 |
| 8 | Estado | badge | 150 |
| 9 | (acciones) | icon button | 56 |

**Placa (componente de marca del producto)**
- Reproduce la placa peruana de forma simple: rectángulo blanco con borde `#0F172A` de 2 px, franja superior azul `#1D4ED8` con el texto “PERÚ” (`caption`, blanco) y la matrícula en `plate` color `#0F172A`. Se ve igual en ambos temas.
- Tamaños: `lg` (detalle y validación, 200 × 72), `md` (cards, 140 × 48), `sm` (tablas: solo texto `mono` dentro de un borde de 1 px, `radius-sm`).
- Variante `a_verificar`: borde `color-warning` discontinuo + ícono `triangle-alert` a la derecha.

**EvidenceViewer**
- Imagen principal con `radius-lg`, fondo `color-surface-sunken`, relación 16:9.
- Superposición inferior con fondo `#0F172AB3`: cámara, fecha/hora (`mono`), confianza.
- Recuadro de detección (borde 2 px `color-accent`) sobre el vehículo y la placa.
- Miniaturas debajo (64 × 40, `radius-md`, activa con borde `color-primary`).
- Controles flotantes: `zoom-in`, `zoom-out`, `eye-off` (difuminar terceros), `download`.

**Timeline (ciclo de vida)**
- Lista vertical: punto de 10 px (color del estado) + línea de 2 px `color-border` + título `body-strong` + hora `mono` `caption` + actor (“Validador: R. Sequeiros”).

**GraphCanvas (mapa del grafo)**
- Lienzo `color-surface-sunken`, `radius-lg`.
- Nodo: círculo de 36 px, `color-graph-node`, borde 2 px `color-graph-node-border`, etiqueta `mono` 12 debajo (“AV-01”). Origen, destino, visitado y ruta con los colores de la sección 3.6.
- Arista: línea de 2 px `color-graph-edge`; etiqueta en el punto medio con “3.0 km · 4 min” (`caption` sobre una pastilla `color-surface`). Ruta: 4 px `color-graph-route`.
- Leyenda flotante abajo a la izquierda; controles flotantes de zoom y capas arriba a la derecha (`elev-2`).
- Las coordenadas de los nodos en el diseño siguen el esquema de la red de ejemplo del plan (sección 4.3).

**CameraCard / CameraRow**
- Nombre (“AV-01 · Av. Javier Prado”), punto de estado (`color-camera-online` / `offline`) + texto (“En línea” / “Sin señal desde 08:31”), fps, última captura, miniatura del stream.

### 8.5 Retroalimentación

**Banner (de sistema o de página)**

| Variante | Fondo | Ícono | Ejemplo de texto |
|---|---|---|---|
| `info` | `color-info-subtle` | `info` | “Modo demostración: los datos son simulados.” |
| `warning` | `color-warning-subtle` | `triangle-alert` | “2 cámaras sin señal. Las capturas de AV-12 y PN-04 están en pausa.” |
| `danger` | `color-danger-subtle` | `circle-x` | “El worker de percepción está desconectado. No se están registrando eventos.” |
| `success` | `color-success-subtle` | `circle-check` | “Grafo actualizado a la versión 2026-10-15.” |

- **Banner de sistema**: ancho completo, encima de la topbar, alto 44, texto `body`, enlace de acción (“Ver cámaras”) y botón cerrar (`x`).
- **Alerta en página**: dentro del contenido, `radius-lg`, borde izquierdo de 4 px del color del estado, título `body-strong` + descripción.

**Toast**
- Ancho 360, `color-surface`, `radius-lg`, `elev-3`, borde `color-border`; ícono de estado + título + descripción opcional + acción (“Deshacer”) + `x`.
- Posición: abajo a la derecha en desktop; abajo y centrado en móvil (por encima de la navegación inferior). Se apilan con gap de 8.
- Ejemplos: “Infracción INF-000123 aprobada · Deshacer”, “Papeleta FP-2026-000123 emitida”.

**Badge**
- `Badge/Estado` (sección 3.4): alto 24, `radius-full`, padding `space-1`/`space-2`, ícono `icon-xs` + texto `caption`.
- `Badge/Count`: mínimo 20 × 20, `radius-full`, `color-primary` con texto blanco `caption` (por ejemplo “12” en Validación).
- `Badge/Live`: punto `color-accent` + “EN VIVO” `overline`.

**Tooltip**: fondo `color-text`, texto `color-text-inverse` `caption`, `radius-md`, padding `space-1`/`space-2`, flecha de 6 px.

**Modal**: ancho 480 (sm) / 640 (md), `radius-xl`, `elev-4`, fondo `color-overlay` detrás. Encabezado `h3` + `x`, cuerpo, pie con acciones a la derecha (secundaria, primaria). Confirmaciones destructivas: “Anular papeleta FP-2026-000123” con campo de motivo obligatorio.

**Drawer / Bottom sheet**: drawer lateral derecho de 480 px en desktop (detalle de cámara, filtros avanzados); bottom sheet en móvil con asa de 32 × 4 px y `radius-xl` arriba.

**Dropdown / Menú**: `color-surface`, `radius-lg`, `elev-2`, ítems de 36 px con ícono `icon-sm`, separadores, ítem destructivo en `color-danger`.

**Progress**: barra lineal de 4 px (`color-primary` sobre `color-surface-muted`) y spinner `loader-circle`.

**Skeleton**: bloques `color-surface-muted` con `radius-md`, imitando la forma real del contenido.

**EmptyState**: ícono `icon-xl` en `color-text-muted` dentro de un círculo de 72 px `color-surface-muted`, título `h3`, descripción `body` `color-text-secondary`, acción opcional.

---

## 9. Patrones globales

### 9.1 Marca
- Ícono `scan-line` blanco dentro de un cuadrado de 32 px `color-primary`, `radius-md`.
- Texto “FotoPapeleta” en `h3` peso 700 + “Inteligente” en `caption` `color-text-muted` debajo.
- Sin logo dibujado a mano. Si el equipo quiere un logo, se genera aparte y se reemplaza el ícono.

### 9.2 Preferencias del usuario (toggles)

Disponibles en **Configuración → Preferencias** y el tema también en la topbar:

| Preferencia | Control | Opciones / efecto |
|---|---|---|
| Tema | SegmentedControl con íconos `sun` / `moon` / `monitor` | Claro · Oscuro · Sistema |
| Densidad | SegmentedControl | Cómoda · Compacta (cambia el eje `density`) |
| Actualizar la cola automáticamente | Switch | Refresca la cola de validación cada 15 s |
| Sonido al llegar una infracción | Switch | — |
| Mostrar atajos de teclado | Switch | Muestra las teclas `A` / `R` / `E` en la barra de decisión |
| Difuminar placas y rostros de terceros | Switch (activado y bloqueado para el portal) | Privacidad (Ley 29733) |
| Notificaciones por correo | Switch + descripción | Resumen diario de pendientes |

**Parámetros del sistema** (solo administrador, en la misma pantalla, sección aparte):
- Tolerancia de velocidad (Slider, 0–15 km/h, por defecto 5).
- Error de reloj por cámara (Input numérico, segundos, por defecto 2).
- Confianza mínima de OCR (Slider, 0.50–0.99, por defecto 0.80).
- Profundidad BFS por defecto `k` (Input numérico, por defecto 2).

### 9.3 Accesibilidad
- Contraste mínimo AA: 4.5:1 en texto normal y 3:1 en texto grande e íconos. Los pares de la sección 3 ya lo cumplen; no inventar combinaciones nuevas.
- Foco visible en todo control: anillo de 2 px `color-focus-ring` con separación de 2 px.
- Nunca comunicar solo con color: estados con ícono y texto; en gráficos, leyenda con texto.
- Botones de solo ícono con etiqueta accesible (“Cerrar”, “Más opciones”) y tooltip.
- Objetivos táctiles de 44 px en móvil (sección 5.3).
- Toda imagen de evidencia lleva un texto alternativo: “Captura de ABC-123 en AV-01, 15/10/2026 08:42:00”.

---

## 10. Pantallas del portal ciudadano (público)

Diseñar cada una en **Desktop (1440)** y **Móvil (390)**, en tema claro y oscuro.

### P1 · Consulta por placa
- **Propósito:** “¿Tengo papeletas?” · **Acción primaria:** Consultar.
- Header del portal → hero centrado (`display` “Consulta tus foto-papeletas”, `body-lg` “Ingresa la placa de tu vehículo para ver infracciones registradas y su evidencia.”) → `PlacaInput` + botón `primary lg` “Consultar” → tres pasos en fila (“Ingresa tu placa” `search`, “Revisa la evidencia” `image`, “Solicita revisión si no estás de acuerdo” `message-square`) → banner `info` “Toda papeleta fue validada por una persona antes de emitirse.” → footer simple.
- Móvil: input y botón a ancho completo; pasos apilados; navegación inferior; FAB oculto en esta pantalla porque el input ya es la acción.

### P2 · Resultados de la consulta
- Encabezado: `Placa/lg` “ABC-123” + “2 papeletas encontradas” + enlace “Nueva consulta”.
- Lista de cards de papeleta: tipo (ícono categórico + nombre), número `FP-2026-000123`, fecha/hora, ubicación, `Badge/Estado`, miniatura de evidencia, botón “Ver detalle”.
- Filtros por chips: Todas · Emitidas · En revisión · Anuladas.
- **Estado vacío:** ícono `circle-check` en `color-success`, “No hay papeletas registradas para ABC-123.”
- **Error:** “No pudimos completar la consulta. Intenta nuevamente.” + “Reintentar”.

### P3 · Detalle de papeleta
- **Región dominante:** `EvidenceViewer` (2/3 del ancho en desktop).
- Columna derecha: card de datos (Número, Placa, Tipo, Fecha y hora, Cámara y ubicación, Velocidad registrada / límite / exceso si aplica), `Badge/Estado`, acciones: `primary` “Descargar PDF” (`download`) y `secondary` “Solicitar revisión” (`message-square`).
- Debajo: **Trayectoria** (mapa con la ruta A\* entre AV-01 y AV-08, “3.0 km en 2 min → 87.1 km/h considerando el margen de error”) y **Timeline** (Detectada → Validada → Emitida).
- Nota de privacidad: “Las placas y rostros de terceros se muestran difuminados.”
- Móvil: imagen arriba a ancho completo, datos debajo, acciones en una barra fija inferior.

### P4 · Solicitar revisión
- Modal (desktop) o pantalla completa (móvil): motivo (Select: “No era mi vehículo”, “Placa mal leída”, “Otro”), descripción (textarea), adjuntar archivo (zona de carga con `upload`), correo de contacto, checkbox de declaración.
- Éxito: card con `circle-check`, “Solicitud registrada con código REV-000045. Te responderemos en un plazo de 7 días hábiles.”

---

## 11. Pantallas del panel administrativo (autenticado)

Diseñar en **Desktop (1440)**; las marcadas también en **Tablet (834)** o **Móvil (390)**. Estructura común: banner de sistema (opcional) + sidebar + topbar + contenido con margen `space-8`.

### A0 · Inicio de sesión
- Dos zonas: izquierda con marca y una frase (“Fiscalización vial con evidencia trazable y validación humana”) sobre `color-primary`; derecha con formulario (Correo, Contraseña con `eye`/`eye-off`, “Recordarme” checkbox, `primary` “Ingresar”). Error: alerta `danger` “Correo o contraseña incorrectos.”
- Móvil: solo el formulario.

### A1 · Resumen (dashboard)
- **Propósito:** ¿cómo está la operación hoy? · **Acción primaria:** “Ir a validación”.
- Fila de 4 `KpiCard`.
- Región dominante: gráfico de barras “Infracciones por hora (hoy)” apiladas por tipo (colores categóricos) + leyenda.
- Lateral: “Cola de validación” (las 5 más antiguas con placa, tipo y tiempo en espera) + botón “Ir a validación”.
- Debajo: “Infracciones por tipo” (barras horizontales) y “Estado de cámaras” (lista compacta con puntos de estado).
- Variante con banner `danger` del worker desconectado.

### A2 · Cámaras
- Mapa (`GraphCanvas` en modo geográfico) a la izquierda (60 %) + tabla/lista de cámaras a la derecha.
- Clic en una cámara → **drawer** con miniatura del stream, estado, fps, última captura, tramos conectados (“AV-08 · 3.0 km · 4 min”) y botón “Editar en admin”.
- Acción primaria: `primary` “Agregar cámara” (`plus`).

### A3 · Infracciones
- Barra de filtros: búsqueda por placa, Select de tipo, Select de estado, DateRange, Select de cámara, botón `ghost` “Más filtros” (abre drawer) + chips de filtros activos.
- Tabla (sección 8.4) con paginación.
- Al seleccionar filas aparece la **barra flotante de acciones**.
- Tablet: columnas Cámara y Confianza ocultas. Móvil: lista de cards.

### A4 · Validación (pantalla clave)
- **Propósito:** decidir si una infracción se emite · **Acción primaria:** Aprobar.
- **Tres columnas:**
  1. **Cola** (320 px): contador “12 pendientes”, orden (Select: “Más antiguas primero”), lista de ítems (placa, tipo, cámara, tiempo de espera, confianza). Ítem activo con `color-primary-subtle`.
  2. **Evidencia** (fill, región dominante): `EvidenceViewer` con las imágenes de **todas las cámaras** donde apareció la placa (pestañas “AV-01 08:42:00” · “AV-08 08:44:00”). Barra de decisión fija abajo.
  3. **Datos y análisis** (400 px): `Placa/lg` con botón `pencil` “Corregir placa”; lecturas de OCR (“ABC-123 · 7 de 8 lecturas · 94 %”); datos del evento; **análisis del grafo** (mini `GraphCanvas` con la ruta, “Ruta mínima 3.0 km · A\* · 3 nodos explorados”, velocidad medida 90.0, conservadora 87.1, límite 60, exceso +27.1 km/h en `color-danger`); evidencia adicional encontrada (“2 cámaras · 1 a verificar”).
- **Rechazar** abre un modal con motivo obligatorio (Select + texto).
- Toast tras decidir: “INF-000123 aprobada · Deshacer” y se carga la siguiente de la cola.
- **Tablet:** cola en drawer, evidencia arriba y datos abajo.

### A5 · Laboratorio del grafo
- **Propósito:** ejecutar y mostrar BFS/DFS/A\* en vivo (exposición) · **Acción primaria:** “Ejecutar”.
- Panel izquierdo (320 px) de parámetros: SegmentedControl algoritmo (BFS · DFS · A\*), Select origen, Select destino (deshabilitado en BFS), Input `k` (solo BFS), SegmentedControl peso (km · min), Switch “Heurística Haversine” (solo A\*), Inputs `max_prof` y `max_rutas` (solo DFS), botón `primary` “Ejecutar” (`play`).
- Centro: `GraphCanvas` mostrando nodos visitados, ruta y orden de exploración (número pequeño sobre cada nodo).
- Abajo: tabla de resultados (Algoritmo, Ruta, Costo, Nodos explorados, Tiempo ms) que acumula ejecuciones para comparar; botón `secondary` “Exportar CSV”.
- Variante con la sección “Velocidad por tramo”: cámara A + hora, cámara B + hora, resultado con medida, conservadora y veredicto (`Badge` “Infracción” / “Sin infracción”).

### A6 · Reportes
- Filtros de periodo + botón `secondary` “Exportar” (`download`).
- Gráficos: infracciones por tipo, por cámara, tasa de aprobación/rechazo, tiempo promedio de validación.
- Tabla resumen por cámara.

### A7 · Configuración
- Tabs: Preferencias · Parámetros del sistema · Usuarios y roles.
- Contenido según la sección 9.2. Cada fila de preferencia: etiqueta + descripción a la izquierda, control a la derecha, divisor entre filas.
- Botón `primary` “Guardar cambios” solo en Parámetros del sistema (las preferencias se aplican al instante con toast).

### A8 · Captura en vivo (móvil, 390)
- Pantalla para el celular que actúa como cámara.
- Vista previa de la cámara a pantalla completa con `Badge/Live` arriba, Select de cámara (“AV-01 · Av. Javier Prado”), indicadores (fps, conexión `wifi`, frames enviados), botón grande circular de iniciar/detener (`play` / `pause`), última placa leída en un toast inferior.
- Estado sin permiso: “Permite el acceso a la cámara para empezar a capturar.” + botón.
- Estado sin conexión: banner `danger` con `wifi-off`.

---

## 12. Estados obligatorios por pantalla

| Pantalla | Cargando | Vacío | Error | Sin permiso | Éxito |
|---|---|---|---|---|---|
| P2 Resultados | Skeleton de 3 cards | “No hay papeletas para ABC-123” | Reintentar | — | — |
| P3 Detalle | Skeleton de imagen + datos | — | “Papeleta no encontrada” | — | — |
| P4 Revisión | Botón en `loading` | — | Errores de campo | — | Card de confirmación |
| A1 Resumen | Skeleton de KPIs y gráfico | “Aún no hay infracciones hoy” | Banner `danger` | — | — |
| A3 Infracciones | Skeleton de filas | “Ninguna infracción coincide con los filtros” + “Limpiar filtros” | Alerta en tabla | — | Toast de acción masiva |
| A4 Validación | Skeleton de 3 columnas | “No hay infracciones pendientes” (`shield-check`) | Alerta | “Tu rol no permite validar” | Toast + siguiente |
| A5 Laboratorio | Botón `loading` | “Elige un origen y ejecuta un algoritmo” | “No existe ruta entre AV-15 y X” | — | Resultado resaltado |
| A8 Captura | “Conectando con la cámara…” | — | Sin conexión | Sin permiso de cámara | Toast con placa leída |

---

## 13. Datos de ejemplo (usar siempre los mismos)

| Dato | Valor |
|---|---|
| Placa principal | `ABC-123` |
| Placa a verificar | `A8C-123` (OCR confundió B/8) |
| Otras placas | `D4F-582`, `BKT-904`, `C2X-117`, `V7M-330` |
| Cámaras | `AV-01` Av. Javier Prado · `AV-08` Av. Arequipa · `AV-02` · `AV-12` Av. Brasil · `AV-15` · `PN-04` |
| Tramos | AV-01–AV-08 3.0 km / 4 min · AV-01–AV-02 2.1 / 3 · AV-08–AV-15 4.5 / 6 · AV-08–AV-12 3.8 / 5 · AV-02–AV-12 5.2 / 7 · AV-12–PN-04 6.0 / 8 |
| Infracción | `INF-000123` · Exceso de velocidad · AV-01 08:42:00 → AV-08 08:44:00 |
| Velocidad | Medida 90.0 km/h · conservadora 87.1 km/h · límite 60 · exceso +27.1 |
| Papeleta | `FP-2026-000123` · emitida 15/10/2026 |
| Solicitud de revisión | `REV-000045` |
| Validadores | T. Hinostroza, R. Sequeiros |
| Formato de fecha y hora | `15/10/2026 08:42:00` (24 h, zona America/Lima) |
| Números | Separador decimal punto en km y km/h (`87.1`), porcentajes sin decimales (`94 %`) |

---

## 14. Framework de frontend — decisión

**Decisión: plantillas de Django + Tailwind CSS v4 + HTMX + Alpine.js + Lucide.** No se usa React ni Angular.

| Pieza | Para qué |
|---|---|
| **Plantillas Django** (+ `django-cotton` para componentes) | Las páginas se generan en el servidor con los datos reales. Cada componente de pencil.dev se convierte en un parcial reutilizable (`<c-button variant="primary">`). |
| **Tailwind CSS v4** | Las variables de este documento se vuelven variables CSS (`--color-primary`, `--space-4`) en el bloque `@theme`. pencil.dev genera código pensando en Tailwind, así que el paso del diseño al código es casi directo. Se compila con el ejecutable independiente de Tailwind (paquete `django-tailwind-cli`), sin instalar Node. |
| **HTMX** | Interactividad con el servidor sin escribir JavaScript: filtrar la tabla, cargar la siguiente infracción de la cola, ejecutar el laboratorio del grafo, actualizar la cola cada 15 s. |
| **Alpine.js** | Interactividad solo de la interfaz: abrir dropdowns, modales y drawers, colapsar la sidebar, switches, cambio de tema y densidad. |
| **Lucide** | Los mismos íconos del diseño, por CDN o como SVG en línea. |
| **Leaflet** (+ OpenStreetMap) | Mapa de cámaras y trayectorias reales. |
| **Chart.js** | Gráficos del resumen y reportes. |

**Por qué no React o Angular:**
- Obligarían a mantener **dos proyectos** (API Django + aplicación de frontend) con su propio build, rutas y autenticación por tokens. Para un equipo de 5 en un APF2 es trabajo extra que no suma nota.
- El prototipo actual es **HTML**: con plantillas Django se reutiliza tal cual y se mejora pantalla por pantalla.
- Angular Material trae su propio lenguaje visual (Material Design), que choca con un diseño propio como este.

**Cuándo sí convendría React:** si el sistema creciera hacia una aplicación muy interactiva (por ejemplo, el laboratorio del grafo con animaciones paso a paso). En ese caso se usaría **React + Vite + Tailwind + shadcn/ui + `lucide-react`** consumiendo la API de Django REST Framework. Este documento sirve igual: las variables, los íconos y los componentes no cambian.

### 14.1 Traducción de variables a código

```css
/* web/static/css/app.css — Tailwind v4 */
@import "tailwindcss";

@theme {
  --font-sans: "Inter", sans-serif;
  --font-mono: "JetBrains Mono", monospace;
  --color-primary: #1D4ED8;
  --color-bg: #F6F7F9;
  --color-surface: #FFFFFF;
  /* … todas las variables de las secciones 3–5 … */
  --radius-md: 8px;
  --spacing: 4px;            /* escala base: p-4 = 16 px */
}

[data-theme="dark"] {
  --color-primary: #2563EB;
  --color-bg: #0B1120;
  --color-surface: #111827;
  /* … */
}

[data-density="compact"] {
  --control-h-md: 36px;
  --table-row-h: 40px;
}
```

- El tema se guarda en `localStorage` y se aplica como `data-theme` en `<html>`; “Sistema” sigue a `prefers-color-scheme`.
- La densidad se aplica como `data-density`.
- Los nombres de variables CSS son **idénticos** a los de pencil.dev (sin el `$`).

### 14.2 Mapa de componentes a parciales Django

| Componente pencil.dev | Parcial (`web/templates/cotton/`) |
|---|---|
| `Button/*` | `button.html` (props: `variant`, `size`, `icon`, `loading`) |
| `Input`, `PlacaInput`, `Select`, `Switch`, `SegmentedControl` | `forms/*.html` |
| `Sidebar`, `SidebarItem`, `Topbar` | `layout/*.html` |
| `Card`, `KpiCard`, `Table`, `Placa`, `EvidenceViewer`, `Timeline` | `data/*.html` |
| `Banner`, `Toast`, `Modal`, `Drawer`, `Badge`, `EmptyState`, `Skeleton` | `feedback/*.html` |
| `GraphCanvas` | `grafo/canvas.html` (SVG generado por el servidor o Leaflet) |

---

## 15. Plan de trabajo en pencil.dev

| Paso | Contenido | Responsable sugerido |
|---|---|---|
| 1 | Variables, temas `mode`/`density`, tipografías | Tonny |
| 2 | Componentes base: Button, Input, Switch, SegmentedControl, Badge, Card, Table, Placa | Tonny / Rodrigo |
| 3 | Navegación: Sidebar, Topbar, header del portal, navegación inferior | Rodrigo |
| 4 | Portal P1–P4 (desktop + móvil) | Yazid |
| 5 | Panel A1, A3, A4 (las pantallas clave para la exposición) | Tonny / Rodrigo |
| 6 | GraphCanvas + A5 Laboratorio + A2 Cámaras | Carlos |
| 7 | A0, A6, A7, A8 | Juan Diego / Yazid |
| 8 | Estados (sección 12) y versión dark de todas las pantallas | Todos |
| 9 | Revisión con la lista de verificación | Juan Diego |

**Prioridad para la exposición:** P1, P3, A1, A4 y A5. Con esas cinco pantallas se cuenta la historia completa: detección → análisis con grafo → validación humana → consulta ciudadana.

---

## 16. Lista de verificación final

**Sistema**
- [ ] Todos los colores, espaciados, radios y tamaños vienen de variables.
- [ ] Ambos temas (`light` / `dark`) y ambas densidades se ven correctamente.
- [ ] Cero emojis; todos los íconos son Lucide y de un mismo grosor.
- [ ] Tipografías: solo Inter y JetBrains Mono.

**Componentes**
- [ ] Cada control tiene los estados default, hover, focus, pressed y disabled (y error/loading cuando aplica).
- [ ] Botones de solo ícono con tooltip.
- [ ] Badges de estado con color + ícono + texto.

**Pantallas**
- [ ] Cada pantalla tiene una sola acción primaria y una región dominante.
- [ ] Ningún contenido recortado ni capas colapsadas; los frames se ajustan al contenido.
- [ ] Objetivos táctiles de 44 px y separación de 8 px en móvil y tablet.
- [ ] Estados de carga, vacío, error y sin permiso diseñados (sección 12).
- [ ] Datos de ejemplo consistentes con la sección 13.
- [ ] Contraste AA verificado en texto, íconos y badges, en ambos temas.
- [ ] Evidencia con terceros difuminados en el portal.
