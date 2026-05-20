/**
 * Widget de chat embebible para la POC de la Guia Medica FIATC.
 * JavaScript vanilla, sin frameworks. Standalone.
 *
 * Uso:
 *   FiatcChat.init({
 *     contenedor: document.getElementById("..."),
 *     endpoint: "http://localhost:8000/chat",
 *     endpointStream: "http://localhost:8000/chat/stream",
 *     saludoInicial: "...",
 *     sugerencias: ["...", "..."]
 *   });
 */
(function (global) {
  "use strict";

  // ── Markdown parser ligero (sin dependencias) ─────────────────────
  function _esc(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function _inline(s) {
    return _esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  }

  function renderMarkdown(text) {
    const lines = text.split("\n");
    const html = [];
    let inList = false;

    for (const raw of lines) {
      const line = raw.trim();

      if (/^---+$/.test(line)) {
        if (inList) { html.push("</ul>"); inList = false; }
        html.push("<hr>");
        continue;
      }

      if (line === "") {
        if (inList) { html.push("</ul>"); inList = false; }
        html.push('<p style="margin:4px 0"></p>');
        continue;
      }

      const listM = line.match(/^[-*•]\s+(.*)/);
      if (listM) {
        if (!inList) { html.push("<ul>"); inList = true; }
        html.push("<li>" + _inline(listM[1]) + "</li>");
        continue;
      }

      if (inList) { html.push("</ul>"); inList = false; }

      const h2 = line.match(/^##\s+(.*)/);
      if (h2) { html.push("<h3>" + _inline(h2[1]) + "</h3>"); continue; }
      const h1 = line.match(/^#\s+(.*)/);
      if (h1) { html.push("<h3>" + _inline(h1[1]) + "</h3>"); continue; }

      html.push("<p>" + _inline(line) + "</p>");
    }

    if (inList) html.push("</ul>");
    return html.join("");
  }

  // ── Helpers ───────────────────────────────────────────────────────
  function _horaActual() {
    return new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  }

  function _crearTimestamp() {
    const t = document.createElement("span");
    t.className = "msg-time";
    t.textContent = _horaActual();
    return t;
  }

  function _crearToolsDebug(herramientas) {
    const debug = document.createElement("div");
    debug.className = "tools-debug";
    debug.textContent = "Herramientas: " + herramientas.join(", ");
    return debug;
  }

  // ── Cards de centros ──────────────────────────────────────────────
  function _renderCentroCard(centro, cfg) {
    const card = document.createElement("div");
    card.className = "centro-card";

    const cabecera = document.createElement("div");
    cabecera.className = "card-cabecera";
    const nombre = document.createElement("div");
    nombre.className = "nombre";
    nombre.textContent = centro.nombre || "(centro sin nombre)";
    cabecera.appendChild(nombre);
    if (centro.preferente) {
      const badge = document.createElement("span");
      badge.className = "badge-preferente";
      badge.textContent = "Preferente";
      cabecera.appendChild(badge);
    }
    card.appendChild(cabecera);

    const partesDireccion = [];
    if (centro.direccion) partesDireccion.push("📍 " + centro.direccion);
    if (centro.poblacion) {
      const cp = centro.codigo_postal ? " (" + centro.codigo_postal + ")" : "";
      partesDireccion.push(centro.poblacion + cp + (centro.provincia ? " · " + centro.provincia : ""));
    }
    if (centro.distancia_km != null) partesDireccion.push("📏 " + centro.distancia_km + " km");
    if (partesDireccion.length) {
      const dir = document.createElement("div");
      dir.className = "meta";
      dir.textContent = partesDireccion.join(" — ");
      card.appendChild(dir);
    }

    if (centro.especialidades && centro.especialidades.length) {
      const esps = document.createElement("div");
      esps.className = "especialidades";
      centro.especialidades.slice(0, 8).forEach(e => {
        if (!e) return;
        const chip = document.createElement("span");
        chip.className = "esp-chip";
        chip.textContent = e;
        esps.appendChild(chip);
      });
      if (centro.especialidades.length > 8) {
        const mas = document.createElement("span");
        mas.className = "esp-chip esp-mas";
        mas.textContent = "+" + (centro.especialidades.length - 8);
        esps.appendChild(mas);
      }
      card.appendChild(esps);
    }

    const acciones = document.createElement("div");
    acciones.className = "acciones";

    if (centro.telefono) {
      const tel = document.createElement("a");
      tel.className = "btn-accion";
      tel.href = "tel:" + centro.telefono.replace(/\s+/g, "");
      tel.textContent = "📞 " + centro.telefono;
      acciones.appendChild(tel);
    }

    const direccionCompleta = [centro.direccion, centro.poblacion, centro.codigo_postal]
      .filter(Boolean).join(", ");
    if (direccionCompleta) {
      const cop = document.createElement("button");
      cop.className = "btn-accion";
      cop.textContent = "📋 Copiar dirección";
      cop.onclick = () => {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(direccionCompleta).then(() => {
            const orig = cop.textContent;
            cop.textContent = "✓ Copiado";
            setTimeout(() => { cop.textContent = orig; }, 1500);
          });
        }
      };
      acciones.appendChild(cop);
    }

    if (centro.latitud != null && centro.longitud != null) {
      const maps = document.createElement("a");
      maps.className = "btn-accion";
      maps.href = "https://www.google.com/maps/search/?api=1&query=" + centro.latitud + "," + centro.longitud;
      maps.target = "_blank";
      maps.rel = "noopener";
      maps.textContent = "🗺️ Cómo llegar";
      acciones.appendChild(maps);
    }

    if (acciones.children.length) card.appendChild(acciones);

    // ── Lista desplegable de profesionales ────────────────────────
    if (centro.profesionales && centro.profesionales.length) {
      const n = centro.profesionales.length;

      const toggle = document.createElement("button");
      toggle.className = "btn-profesionales-toggle";
      toggle.innerHTML = `<span class="toggle-icon">▶</span> Ver profesionales (${n})`;
      card.appendChild(toggle);

      const lista = document.createElement("div");
      lista.className = "profesionales-lista";
      lista.hidden = true;

      centro.profesionales.forEach(doc => {
        const item = document.createElement("div");
        item.className = "profesional-item";

        const info = document.createElement("div");
        info.className = "profesional-info";

        const nombre = document.createElement("span");
        nombre.className = "prof-nombre";
        nombre.textContent = doc.nombre;
        info.appendChild(nombre);

        const esps = (doc.especialidades || []);
        if (esps.length) {
          const espEl = document.createElement("span");
          espEl.className = "prof-esps";
          espEl.textContent = esps.join(" · ");
          info.appendChild(espEl);
        }

        item.appendChild(info);

        if (doc.reserva_online && cfg.endpointReserva && doc.ref) {
          const cita = document.createElement("button");
          cita.className = "btn-reserva-cita";
          cita.innerHTML = "&#128197; Reservar Cita";
          cita.addEventListener("click", () => {
            // Extraer prof, consul y codi_esp del ref (número de 18 dígitos al final)
            const refNum = (doc.ref.match(/(\d{18})$/) || [])[1] || "";
            const profCode  = refNum ? String(parseInt(refNum.substring(0, 5),  10)) : (doc.prof || "");
            const consulCode = refNum ? refNum.substring(10, 15) : (centro.consul || "");
            const codiEsp   = refNum ? String(parseInt(refNum.substring(15, 18), 10)) : "";

            // Construir el JSON que espera el sistema de reservas
            const payload = {
              ccita:               "1",
              telefon1:            centro.telefono  || "",
              telefon2:            "",
              codi_esp:            codiEsp,
              lng:                 String(centro.longitud || ""),
              direccio:            (centro.direccion  || "").toUpperCase(),
              horari:              centro.horario    || "",
              lit_prov:            (centro.provincia || "").toUpperCase(),
              nom:                 (doc.nombre       || "").toUpperCase(),
              nom_propi:           (centro.nombre    || "").toUpperCase(),
              codi_postal:         centro.codigo_postal || "",
              lat:                 String(centro.latitud || ""),
              subespecialitats:    "",
              subespecialitatsList: [],
              prof:                profCode,
              consul:              consulCode,
              dental:              "",
              quadre:              "",
              fact:                centro.fact || "",
              prior:               0,
              spremium:            "N",
              lit_esp:             (doc.especialidades[0] || "").toUpperCase().padEnd(80),
              lit_esp_url:         (doc.especialidades[0] || "").toLowerCase()
                                     .replace(/\.\s*/g, "-").replace(/\s+/g, "-").replace(/-+/g, "-"),
              lit_pob:             (centro.poblacion || "").toUpperCase(),
              codi_prov:           -1,
              te_sub_esps_rel:     false,
              te_dental_info_rel:  false,
              ref:                 doc.ref,
              visibilidadNacional: false,
            };

            // Base64 UTF-8 compatible (btoa solo acepta Latin-1)
            const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
            const url = cfg.endpointReserva + "#sld_guia_medica/autorizacion2/centro=" + b64;
            window.open(url, "_blank", "noopener,noreferrer");
          });
          item.appendChild(cita);
        }

        lista.appendChild(item);
      });

      toggle.addEventListener("click", () => {
        const abierto = !lista.hidden;
        lista.hidden = abierto;
        toggle.innerHTML = abierto
          ? `<span class="toggle-icon">▶</span> Ver profesionales (${n})`
          : `<span class="toggle-icon open">▼</span> Ocultar profesionales`;
      });

      card.appendChild(lista);
    }

    return card;
  }

  // ── Mapa Leaflet ──────────────────────────────────────────────────
  function _renderMapa(centros, contenedor) {
    if (typeof L === "undefined") return null;

    const conCoords = centros.filter(c => c.latitud != null && c.longitud != null);
    if (!conCoords.length) return null;

    const mapDiv = document.createElement("div");
    mapDiv.className = "centro-mapa";
    contenedor.appendChild(mapDiv);

    // Esperar al siguiente paint para que Leaflet calcule el tamaño correctamente
    requestAnimationFrame(() => {
      const map = L.map(mapDiv, { scrollWheelZoom: false }).setView(
        [conCoords[0].latitud, conCoords[0].longitud],
        14
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      const bounds = [];
      conCoords.forEach(c => {
        const m = L.marker([c.latitud, c.longitud]).addTo(map);
        const pop = `<strong>${_esc(c.nombre || "")}</strong><br>` +
          (c.direccion ? _esc(c.direccion) + "<br>" : "") +
          (c.telefono ? "📞 " + _esc(c.telefono) : "");
        m.bindPopup(pop);
        bounds.push([c.latitud, c.longitud]);
      });

      if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [25, 25] });
      }
    });

    return mapDiv;
  }

  // ── Widget principal ──────────────────────────────────────────────
  const FiatcChat = {
    init(opciones) {
      const cfg = Object.assign(
        {
          endpoint: "http://localhost:8000/chat",
          endpointStream: null,
          // URL base del sistema de reservas online. Se le añaden ?consul=XXXXX&codi_esp=XXX.
          // Si está vacío, el botón "Reservar Cita" no aparece.
          endpointReserva: "",
          saludoInicial: "Hola. ¿En qué te puedo ayudar con el cuadro médico de FIATC?",
          sugerencias: [],
        },
        opciones || {}
      );
      if (!cfg.contenedor) {
        console.error("FiatcChat.init: falta opcion 'contenedor'");
        return;
      }
      construir(cfg);
    },
  };

  const MAX_HISTORIAL_MENSAJES = 10; // 5 turnos usuario/asistente

  function construir(cfg) {
    const root = cfg.contenedor;
    const usaStreaming = !!cfg.endpointStream;

    function montar() {
      root.innerHTML = "";
      root.classList.add("chat");

      // Toolbar
      const toolbar = document.createElement("div");
      toolbar.className = "chat-toolbar";
      const btnReset = document.createElement("button");
      btnReset.className = "btn-reset";
      btnReset.textContent = "Nueva consulta";
      btnReset.onclick = montar;
      toolbar.appendChild(btnReset);
      root.appendChild(toolbar);

      const mensajes = document.createElement("div");
      mensajes.className = "chat-mensajes";
      root.appendChild(mensajes);


      const inputArea = document.createElement("div");
      inputArea.className = "input-area";
      const input = document.createElement("textarea");
      input.rows = 1;
      input.placeholder = "Escribe tu pregunta… (Shift+Intro para salto de línea)";
      function _ajustarAlturaTextarea() {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 120) + "px";
      }
      input.addEventListener("input", _ajustarAlturaTextarea);
      // Altura inicial (antes de que el usuario escriba)
      requestAnimationFrame(_ajustarAlturaTextarea);
      const boton = document.createElement("button");
      boton.textContent = "Enviar";
      inputArea.appendChild(input);
      inputArea.appendChild(boton);
      root.appendChild(inputArea);

      const historial = [];

      function pintar(role, texto, herramientas, esHtml) {
        const div = document.createElement("div");
        div.className = "msg " + (role === "user" ? "user" : "bot");

        if (esHtml) {
          div.innerHTML = renderMarkdown(texto);
        } else {
          div.textContent = texto;
        }

        if (herramientas && herramientas.length) {
          div.appendChild(_crearToolsDebug(herramientas));
        }
        div.appendChild(_crearTimestamp());

        mensajes.appendChild(div);
        mensajes.scrollTop = mensajes.scrollHeight;
        return div;
      }

      function mostrarCargando() {
        const div = document.createElement("div");
        div.className = "msg bot cargando";
        div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
        mensajes.appendChild(div);
        mensajes.scrollTop = mensajes.scrollHeight;
        return div;
      }

      function crearBurbujaBot() {
        const div = document.createElement("div");
        div.className = "msg bot";
        const contenido = document.createElement("div");
        contenido.className = "bot-contenido";
        div.appendChild(contenido);
        mensajes.appendChild(div);
        mensajes.scrollTop = mensajes.scrollHeight;
        return { elemento: div, contenido };
      }

      function nombreToolBonito(name) {
        const map = {
          buscar_profesionales: "Buscando profesionales…",
          geolocalizar: "Localizando ubicación…",
          mapear_sintoma_a_especialidad: "Identificando especialidad…",
          listar_especialidades: "Consultando especialidades…",
        };
        return map[name] || ("Ejecutando " + name + "…");
      }

      // ── Streaming ────────────────────────────────────────────────
      async function enviarStream(valor) {
        let typing = mostrarCargando();
        let burbuja = null;
        let acumulado = "";
        const herramientas = [];
        let centrosFinales = null;
          let centrosPreferentes = null;

        try {
          const resp = await fetch(cfg.endpointStream, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mensaje: valor,
              historial: historial.slice(0, -1).slice(-MAX_HISTORIAL_MENSAJES),
            }),
          });
          if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);

          const reader = resp.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const partes = buffer.split("\n\n");
            buffer = partes.pop();

            for (const ev of partes) {
              const linea = ev.split("\n").find(l => l.startsWith("data: "));
              if (!linea) continue;
              const json = linea.slice(6).trim();
              if (!json) continue;
              let payload;
              try { payload = JSON.parse(json); } catch { continue; }

              if (payload.type === "delta") {
                if (typing) { typing.remove(); typing = null; }
                if (!burbuja) burbuja = crearBurbujaBot();
                acumulado += payload.text;
                burbuja.contenido.innerHTML = renderMarkdown(acumulado);
                mensajes.scrollTop = mensajes.scrollHeight;
              } else if (payload.type === "tool") {
                herramientas.push(payload.name);
                if (typing) {
                  typing.querySelector(".typing-dots")?.insertAdjacentHTML(
                    "afterend",
                    `<span class="tool-status">${_esc(nombreToolBonito(payload.name))}</span>`
                  );
                }
              } else if (payload.type === "preferentes") {
                centrosPreferentes = payload.items || [];
              } else if (payload.type === "centros") {
                centrosFinales = payload.items || [];
              } else if (payload.type === "done") {
                if (typing) { typing.remove(); typing = null; }
                if (burbuja) {
                  // Markdown final + cards + mapa
                  burbuja.contenido.innerHTML = renderMarkdown(acumulado);
                  if (centrosPreferentes && centrosPreferentes.length) {
                    const secPref = document.createElement("div");
                    secPref.className = "seccion-preferentes";
                    const titulo = document.createElement("div");
                    titulo.className = "preferentes-titulo";
                    titulo.textContent = "⭐ Centros preferentes cercanos";
                    secPref.appendChild(titulo);
                    const cardsWrapPref = document.createElement("div");
                    cardsWrapPref.className = "centros-cards";
                    centrosPreferentes.forEach(c => cardsWrapPref.appendChild(_renderCentroCard(c, cfg)));
                    secPref.appendChild(cardsWrapPref);
                    burbuja.elemento.appendChild(secPref);
                  }
                  if (centrosFinales && centrosFinales.length) {
                    if (centrosPreferentes && centrosPreferentes.length) {
                      const titNorm = document.createElement("div");
                      titNorm.className = "normales-titulo";
                      titNorm.textContent = "Otros centros";
                      burbuja.elemento.appendChild(titNorm);
                    }
                    const cardsWrap = document.createElement("div");
                    cardsWrap.className = "centros-cards";
                    centrosFinales.forEach(c => cardsWrap.appendChild(_renderCentroCard(c, cfg)));
                    burbuja.elemento.appendChild(cardsWrap);
                    _renderMapa([...(centrosPreferentes || []), ...centrosFinales], burbuja.elemento);
                  }
                  if (herramientas.length) {
                    burbuja.elemento.appendChild(_crearToolsDebug(herramientas));
                  }
                  burbuja.elemento.appendChild(_crearTimestamp());
                }
                if (acumulado) historial.push({ role: "assistant", content: acumulado });
              } else if (payload.type === "error") {
                if (typing) { typing.remove(); typing = null; }
                pintar("bot", "Error: " + payload.message, null, false);
              }
            }
          }
        } catch (err) {
          if (typing) typing.remove();
          if (burbuja) burbuja.elemento.remove();
          pintar(
            "bot",
            "No he podido conectar con el backend. Comprueba que el servidor está arrancado.",
            null,
            false
          );
          console.error(err);
        }
      }

      // ── Modo bloqueante (fallback) ──────────────────────────────
      async function enviarBloqueante(valor) {
        const cargando = mostrarCargando();
        try {
          const resp = await fetch(cfg.endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mensaje: valor,
              historial: historial.slice(0, -1).slice(-MAX_HISTORIAL_MENSAJES),
            }),
          });
          const data = await resp.json();
          cargando.remove();
          const texto = data.respuesta || "(sin respuesta)";
          pintar("bot", texto, data.herramientas_usadas, true);
          historial.push({ role: "assistant", content: texto });
        } catch (err) {
          cargando.remove();
          pintar("bot", "No he podido conectar con el backend.", null, false);
          console.error(err);
        }
      }

      let divSugerencias = null;

      function ocultarSugerencias() {
        if (divSugerencias) {
          divSugerencias.remove();
          divSugerencias = null;
        }
      }

      async function enviar(texto) {
        const valor = (texto || input.value || "").trim();
        if (!valor) return;
        input.value = "";
        _ajustarAlturaTextarea();
        ocultarSugerencias();

        pintar("user", valor, null, false);
        historial.push({ role: "user", content: valor });
        boton.disabled = true;

        try {
          if (usaStreaming) {
            await enviarStream(valor);
          } else {
            await enviarBloqueante(valor);
          }
        } finally {
          boton.disabled = false;
          input.focus();
        }
      }

      boton.onclick = () => enviar();
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          enviar();
        }
      });

      pintar("bot", cfg.saludoInicial, null, false);

      if (cfg.sugerencias.length) {
        divSugerencias = document.createElement("div");
        divSugerencias.className = "sugerencias";
        cfg.sugerencias.forEach((texto) => {
          const btn = document.createElement("button");
          btn.textContent = texto;
          btn.onclick = () => enviar(texto);
          divSugerencias.appendChild(btn);
        });
        mensajes.appendChild(divSugerencias);
        mensajes.scrollTop = mensajes.scrollHeight;
      }

      input.focus();
    }

    montar();
  }

  global.FiatcChat = FiatcChat;
})(window);
