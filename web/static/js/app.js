/* FotoPapeleta Inteligente — interacción solo de interfaz (Alpine.js).
   Lo que depende del servidor va por HTMX o formularios normales. */

const fpPrefs = {
  leer(clave, defecto) {
    try { const v = localStorage.getItem("fp-" + clave); return v === null ? defecto : JSON.parse(v); }
    catch { return defecto; }
  },
  guardar(clave, valor) {
    try { localStorage.setItem("fp-" + clave, JSON.stringify(valor)); } catch { /* modo privado */ }
  },
};

function fpAplicarTema(tema) {
  const oscuro = tema === "oscuro" || (tema === "sistema" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = oscuro ? "dark" : "light";
}

matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => fpAplicarTema(fpPrefs.leer("tema", "sistema")));

document.addEventListener("alpine:init", () => {
  Alpine.store("prefs", {
    tema: fpPrefs.leer("tema", "sistema"),
    densidad: fpPrefs.leer("densidad", "comoda"),
    autoCola: fpPrefs.leer("autoCola", true),
    atajos: fpPrefs.leer("atajos", true),
    get oscuro() { return document.documentElement.dataset.theme === "dark"; },
    fijar(clave, valor, aviso) {
      this[clave] = valor;
      fpPrefs.guardar(clave, valor);
      if (clave === "tema") fpAplicarTema(valor);
      if (clave === "densidad") document.documentElement.dataset.density = valor === "compacta" ? "compact" : "comfortable";
      if (aviso) Alpine.store("toasts").agregar("success", "Preferencia guardada", aviso);
    },
    alternarTema() { this.fijar("tema", this.oscuro ? "claro" : "oscuro"); },
  });

  Alpine.store("toasts", {
    lista: [],
    n: 0,
    agregar(tipo, titulo, texto = "", accion = null) {
      const id = ++this.n;
      this.lista.push({ id, tipo, titulo, texto, accion });
      setTimeout(() => this.quitar(id), 6000);
    },
    quitar(id) { this.lista = this.lista.filter(t => t.id !== id); },
  });

  /* Placa corregida por el validador antes de aprobar (pantalla A4) */
  Alpine.store("correccion", "");

  /* Historial local de placas consultadas en el portal ("Mis consultas"); no sale del navegador. */
  Alpine.store("historial", {
    placas: fpPrefs.leer("consultas", []),
    agregar(placa) {
      if (!placa) return;
      this.placas = [placa, ...this.placas.filter(p => p !== placa)].slice(0, 10);
      fpPrefs.guardar("consultas", this.placas);
    },
    limpiar() { this.placas = []; fpPrefs.guardar("consultas", []); },
  });
});

/* Ctrl K (o /) enfoca la búsqueda global del panel */
document.addEventListener("keydown", (e) => {
  const enCampo = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" || (e.key === "/" && !enCampo)) {
    const buscador = document.getElementById("busqueda-global");
    if (buscador) { e.preventDefault(); buscador.focus(); buscador.select(); }
  }
});

/* Mensajes de Django -> toasts */
document.addEventListener("alpine:initialized", () => {
  document.querySelectorAll("[data-mensaje]").forEach(m =>
    Alpine.store("toasts").agregar(m.dataset.tipo, m.dataset.mensaje, m.dataset.detalle || ""));
});

/* CSRF para peticiones HTMX */
document.addEventListener("htmx:configRequest", (e) => {
  const token = document.querySelector("meta[name=csrf-token]")?.content;
  if (token) e.detail.headers["X-CSRFToken"] = token;
});

function fpCopiar(texto, aviso = "Copiado al portapapeles") {
  navigator.clipboard?.writeText(texto).then(() => Alpine.store("toasts").agregar("success", aviso, texto));
}

/* Recorrido guiado (driver.js): automático la primera vez en cada pantalla; el botón «?» lo repite. */
function fpTutorial(manual = false) {
  const nodo = document.getElementById("datos-tutorial");
  if (!nodo || !window.driver?.js) return;
  const datos = JSON.parse(nodo.textContent);
  const visible = (sel) => {  // en pantalla: descarta lo oculto y lo que está fuera (p. ej. el menú cerrado en el celular)
    const r = document.querySelector(sel)?.getBoundingClientRect();
    return r && r.width > 0 && r.height > 0 && r.right > 0 && r.left < innerWidth;
  };
  const pasos = (manual ? datos.manual : datos.auto)
    .filter(p => !p.tour || visible(`[data-tour="${p.tour}"]`))
    .map(p => ({ element: p.tour ? `[data-tour="${p.tour}"]` : undefined,
                 popover: { title: p.titulo, description: p.texto, side: p.lado === "over" ? undefined : p.lado, align: "start" } }));
  if (!pasos.length) return;
  const recorrido = window.driver.js.driver({
    showProgress: pasos.length > 1, progressText: "{{current}} de {{total}}",
    nextBtnText: "Siguiente", prevBtnText: "Anterior", doneBtnText: "Entendido",
    popoverClass: "fp-tour", overlayOpacity: 0.55, stagePadding: 6, stageRadius: 10, smoothScroll: true,
    steps: pasos,
    onDestroyed: () => {
      if (manual) return;
      const cuerpo = new FormData();
      cuerpo.append("pantalla", datos.pantalla);
      if (datos.primera) cuerpo.append("primera", "1");
      fetch(datos.url, { method: "POST", body: cuerpo,
        headers: { "X-CSRFToken": document.querySelector("meta[name=csrf-token]")?.content || "" } });
    },
  });
  recorrido.drive();
}

document.addEventListener("alpine:initialized", () => {
  const nodo = document.getElementById("datos-tutorial");
  if (nodo && JSON.parse(nodo.textContent).auto.length) setTimeout(() => fpTutorial(false), 500);
});
