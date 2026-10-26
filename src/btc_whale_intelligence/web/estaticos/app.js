/**
 * BTC WHALE INTELLIGENCE — CLIENT-SIDE SPA LOGIC
 */

let chartCategorias = null;
let chartVolumen = null;
let eventosCargados = [];

document.addEventListener("DOMContentLoaded", () => {
    cargarResumen();
    cargarEventos();
    cargarEntidades();
    cargarPredicciones();

    // Actualización automática cada 30 segundos
    setInterval(() => {
        cargarResumen();
        cargarEventos(false);
    }, 30000);
});

function cambiarTab(tabId, btn) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) {
        targetTab.classList.add("active");
    }
    btn.classList.add("active");

    if (tabId === "grafico") {
        setTimeout(actualizarGraficos, 50);
    }
}

async function cargarResumen() {
    try {
        const resp = await fetch("/api/resumen");
        if (!resp.ok) return;
        const data = await resp.json();

        // Ticker Header
        const elPrice = document.getElementById("btc-price");
        if (elPrice && data.precio_btc_usd) {
            elPrice.textContent = `$${data.precio_btc_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
        }

        const elChange = document.getElementById("btc-change");
        if (elChange && data.variacion_24h_pct !== undefined) {
            const signo = data.variacion_24h_pct >= 0 ? "+" : "";
            elChange.textContent = `${signo}${data.variacion_24h_pct.toFixed(2)}%`;
            elChange.className = `ticker-change ${data.variacion_24h_pct < 0 ? "negativo" : ""}`;
        }

        // KPIs
        const elVolBtc = document.getElementById("kpi-volumen-btc");
        if (elVolBtc) {
            elVolBtc.innerHTML = `${data.volumen_total_movido_btc.toLocaleString("en-US", { minimumFractionDigits: 2 })} <span class="unit">BTC</span>`;
        }

        const elVolUsd = document.getElementById("kpi-volumen-usd");
        if (elVolUsd && data.volumen_total_usd) {
            elVolUsd.textContent = `≈ $${data.volumen_total_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })} USD`;
        }

        const elEventos = document.getElementById("kpi-total-eventos");
        if (elEventos) elEventos.textContent = data.total_eventos_detectados;

        const elEntidades = document.getElementById("kpi-total-entidades");
        if (elEntidades) elEntidades.textContent = data.total_entidades_vigiladas;

        const elPred = document.getElementById("kpi-total-predicciones");
        if (elPred) elPred.textContent = data.total_predicciones_registradas;

    } catch (err) {
        console.error("Error al cargar resumen:", err);
    }
}

async function cargarEventos(mostrarSpinner = true) {
    const tbody = document.getElementById("tabla-eventos-body");
    const filtro = document.getElementById("filtro-categoria").value;
    const badgeCount = document.getElementById("count-eventos");

    if (mostrarSpinner && tbody) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center loading-cell">Cargando movimientos on-chain...</td></tr>`;
    }

    try {
        let url = "/api/eventos?limite=100";
        if (filtro) url += `&categoria=${encodeURIComponent(filtro)}`;

        const resp = await fetch(url);
        if (!resp.ok) throw new Error("Error en respuesta de API");
        const eventos = await resp.json();
        eventosCargados = eventos;

        if (badgeCount) badgeCount.textContent = `${eventos.length} registros`;

        if (!tbody) return;

        if (eventos.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center loading-cell">No se encontraron movimientos registrados con este filtro.</td></tr>`;
            return;
        }

        tbody.innerHTML = eventos.map(ev => {
            const fechaStr = ev.fecha_utc ? new Date(ev.fecha_utc).toLocaleString("es-ES", { timeZone: "UTC" }) + " UTC" : "-";
            const txCorta = ev.txid ? `${ev.txid.substring(0, 8)}...${ev.txid.substring(ev.txid.length - 6)}` : "-";
            const enlaceMempool = `https://mempool.space/tx/${ev.txid}`;
            const enlaceBtcscan = `https://btcscan.org/tx/${ev.txid}`;

            const s24 = ev.senal_24h || { direccion: "NEUTRAL", retorno_esperado_pct: 0.0 };
            const s7 = ev.senal_7d || { direccion: "NEUTRAL", retorno_esperado_pct: 0.0 };

            const signo24 = s24.retorno_esperado_pct > 0 ? "+" : "";
            const signo7 = s7.retorno_esperado_pct > 0 ? "+" : "";

            const icono24 = s24.direccion === "ALCISTA" ? "▲" : s24.direccion === "BAJISTA" ? "▼" : "■";
            const icono7 = s7.direccion === "ALCISTA" ? "▲" : s7.direccion === "BAJISTA" ? "▼" : "■";

            const destinoTokenBadge = ev.token_destino && ev.token_destino.includes("Exchange") 
                ? `<span style="color:#38bdf8;">Exchange USDT</span>` 
                : `<span class="token-symbol">BTC</span>`;

            return `
                <tr>
                    <td style="color: var(--text-muted); font-size: 11px; white-space: nowrap;">${fechaStr}</td>
                    <td>
                        <div class="monto-btc">${ev.monto_btc.toLocaleString("en-US", { minimumFractionDigits: 2 })} BTC</div>
                        <div class="valor-usd">≈ $${ev.valor_usd ? ev.valor_usd.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "0"} USD</div>
                    </td>
                    <td>
                        <span class="badge-token" title="${ev.nota_tokens || 'Bitcoin L1 UTXO'}">
                            <span class="token-symbol">BTC</span> ➔ ${destinoTokenBadge}
                        </span>
                    </td>
                    <td><span class="badge-cat ${ev.categoria}">${ev.categoria}</span></td>
                    <td style="font-weight: 500; font-size: 12px;">${ev.entidad_origen}</td>
                    <td style="font-weight: 500; font-size: 12px;">${ev.entidad_destino}</td>
                    <td>
                        <span class="badge-signal ${s24.direccion}">
                            ${icono24} ${s24.direccion} ${signo24}${s24.retorno_esperado_pct.toFixed(1)}%
                        </span>
                    </td>
                    <td>
                        <span class="badge-signal ${s7.direccion}">
                            ${icono7} ${s7.direccion} ${signo7}${s7.retorno_esperado_pct.toFixed(1)}%
                        </span>
                    </td>
                    <td>
                        <div class="explorer-group">
                            <a href="${enlaceBtcscan}" target="_blank" class="explorer-link" title="Ver en BTCScan.org">BTCScan ↗</a>
                            <a href="${enlaceMempool}" target="_blank" class="explorer-link" title="Ver en Mempool.space">Mempool ↗</a>
                        </div>
                    </td>
                    <td>
                        <button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="verDetalleEvento(${ev.id})">
                            Detalle
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        actualizarGraficos();

    } catch (err) {
        console.error("Error al cargar eventos:", err);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center loading-cell" style="color: var(--accent-rose);">Error al conectar con la base de datos.</td></tr>`;
        }
    }
}

async function cargarEntidades() {
    const grid = document.getElementById("entity-grid");
    if (!grid) return;

    try {
        const resp = await fetch("/api/entidades");
        if (!resp.ok) return;
        const entidades = await resp.json();

        if (entidades.length === 0) {
            grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">No hay entidades registradas aún.</div>`;
            return;
        }

        grid.innerHTML = entidades.map(e => `
            <div class="entity-card glassmorphism">
                <div class="entity-card-header">
                    <span class="entity-card-title">${e.nombre}</span>
                    <span class="entity-type-badge">${e.categoria}</span>
                </div>
                <div class="entity-detail-row">
                    <span class="entity-detail-label">Confianza de atribución:</span>
                    <strong style="color: var(--accent-emerald);">${(e.nivel_confianza * 100).toFixed(0)}%</strong>
                </div>
                <div class="entity-detail-row">
                    <span class="entity-detail-label">Direcciones rastreadas:</span>
                    <strong>${e.total_direcciones}</strong>
                </div>
                <div class="entity-detail-row">
                    <span class="entity-detail-label">Umbral personalizado:</span>
                    <strong>${e.umbral_btc ? e.umbral_btc + ' BTC' : 'General'}</strong>
                </div>
                <div style="margin-top: 10px; font-size: 11px; color: var(--text-dim); line-height: 1.3;">
                    <em>Fuente: ${e.fuentes || 'Pública'}</em>
                </div>
            </div>
        `).join("");

    } catch (err) {
        console.error("Error al cargar entidades:", err);
    }
}

async function cargarPredicciones() {
    const tbody = document.getElementById("tabla-predicciones-body");
    if (!tbody) return;

    try {
        const resp = await fetch("/api/predicciones");
        if (!resp.ok) return;
        const preds = await resp.json();

        if (preds.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center loading-cell">No hay predicciones pre-registradas aún.</td></tr>`;
            return;
        }

        tbody.innerHTML = preds.map(p => {
            const fechaReg = p.fecha_registro_utc ? new Date(p.fecha_registro_utc).toLocaleString("es-ES", { timeZone: "UTC" }) : "-";
            const fechaVenc = p.fecha_vencimiento_utc ? new Date(p.fecha_vencimiento_utc).toLocaleString("es-ES", { timeZone: "UTC" }) : "-";

            let resultadoTd = `<span style="color: var(--accent-amber);">En curso / Calibración</span>`;
            let bhTd = `-`;
            let persTd = `-`;
            let pFinalTd = `-`;

            if (p.resultado) {
                const ret = p.resultado.retorno_real_pct;
                const retColor = ret >= 0 ? "var(--accent-emerald)" : "var(--accent-rose)";
                const retSigno = ret >= 0 ? "+" : "";
                resultadoTd = `<strong style="color: ${retColor}">${retSigno}${ret.toFixed(2)}% (${p.resultado.resultado_categoria})</strong>`;
                bhTd = `${p.resultado.baseline_buy_hold_pct ? (p.resultado.baseline_buy_hold_pct >= 0 ? '+' : '') + p.resultado.baseline_buy_hold_pct.toFixed(2) + '%' : '-'}`;
                persTd = `0.00%`;
                pFinalTd = p.resultado.precio_final_usd ? `$${p.resultado.precio_final_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "-";
            }

            return `
                <tr>
                    <td style="color: var(--text-dim);">#${p.id}</td>
                    <td><strong style="color: var(--primary-cyan);">${p.horizonte}</strong></td>
                    <td>$${p.precio_inicial_usd ? p.precio_inicial_usd.toLocaleString("en-US", { minimumFractionDigits: 2 }) : "-"}</td>
                    <td><span class="badge-cat INCIERTA">${p.tipo_estimacion}</span></td>
                    <td style="font-size: 11px; color: var(--text-muted);">${fechaVenc}</td>
                    <td>${pFinalTd}</td>
                    <td>${resultadoTd}</td>
                    <td style="color: var(--text-muted);">${bhTd}</td>
                    <td style="color: var(--text-muted);">${persTd}</td>
                </tr>
            `;
        }).join("");

    } catch (err) {
        console.error("Error al cargar predicciones:", err);
    }
}

function actualizarGraficos() {
    if (!eventosCargados || eventosCargados.length === 0) return;

    // 1. Agrupar categorías
    const conteoCategorias = {};
    const volumenCategorias = {};

    eventosCargados.forEach(e => {
        conteoCategorias[e.categoria] = (conteoCategorias[e.categoria] || 0) + 1;
        volumenCategorias[e.categoria] = (volumenCategorias[e.categoria] || 0) + e.monto_btc;
    });

    const labels = Object.keys(conteoCategorias);
    const dataConteo = Object.values(conteoCategorias);
    const dataVolumen = Object.values(volumenCategorias);

    const colores = [
        "rgba(244, 63, 94, 0.75)",
        "rgba(16, 185, 129, 0.75)",
        "rgba(6, 182, 212, 0.75)",
        "rgba(147, 51, 234, 0.75)",
        "rgba(148, 163, 184, 0.75)"
    ];

    // Chart 1: Donut Categorías
    const canvas1 = document.getElementById("chart-categorias");
    if (canvas1) {
        if (chartCategorias) chartCategorias.destroy();
        chartCategorias = new Chart(canvas1, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: dataConteo,
                    backgroundColor: colores.slice(0, labels.length),
                    borderColor: "#111827",
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
                    }
                }
            }
        });
    }

    // Chart 2: Barras Volumen
    const canvas2 = document.getElementById("chart-volumen");
    if (canvas2) {
        if (chartVolumen) chartVolumen.destroy();
        chartVolumen = new Chart(canvas2, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Volumen BTC",
                    data: dataVolumen,
                    backgroundColor: "rgba(6, 182, 212, 0.65)",
                    borderColor: "#06b6d4",
                    borderWidth: 1,
                    borderRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#94a3b8", font: { family: "Inter", size: 10 } }, grid: { display: false } },
                    y: { ticks: { color: "#94a3b8", font: { family: "Inter" } }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
}

function verDetalleEvento(eventoId) {
    const ev = eventosCargados.find(x => x.id === eventoId);
    if (!ev) return;

    const modalTitulo = document.getElementById("modal-titulo");
    const modalContenido = document.getElementById("modal-contenido");

    if (modalTitulo) modalTitulo.textContent = `Movimiento #${ev.id} — ${ev.monto_btc.toFixed(4)} BTC (≈ $${ev.valor_usd ? ev.valor_usd.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "0"} USD)`;

    const s24 = ev.senal_24h || {};
    const s7 = ev.senal_7d || {};
    const s30 = ev.senal_30d || {};

    const enlaceMempoolTx = `https://mempool.space/tx/${ev.txid}`;
    const enlaceBtcscanTx = `https://btcscan.org/tx/${ev.txid}`;

    const dirInHtml = ev.direccion_origen ? `
        <div style="margin-top: 4px; font-family: var(--font-mono); font-size: 11px;">
            <span style="color: var(--text-dim);">Dirección Origen:</span> 
            <a href="https://btcscan.org/address/${ev.direccion_origen}" target="_blank" style="color: var(--primary-cyan);">${ev.direccion_origen}</a>
            <span style="color: var(--text-muted); font-size: 10px;">(BTCScan ↗ | <a href="https://mempool.space/address/${ev.direccion_origen}" target="_blank" style="color: var(--primary-cyan);">Mempool ↗</a>)</span>
        </div>
    ` : '';

    const dirOutHtml = ev.direccion_destino ? `
        <div style="margin-top: 4px; font-family: var(--font-mono); font-size: 11px;">
            <span style="color: var(--text-dim);">Dirección Destino:</span> 
            <a href="https://btcscan.org/address/${ev.direccion_destino}" target="_blank" style="color: var(--primary-cyan);">${ev.direccion_destino}</a>
            <span style="color: var(--text-muted); font-size: 10px;">(BTCScan ↗ | <a href="https://mempool.space/address/${ev.direccion_destino}" target="_blank" style="color: var(--primary-cyan);">Mempool ↗</a>)</span>
        </div>
    ` : '';

    if (modalContenido) {
        modalContenido.innerHTML = `
            <!-- 1. Activo y Flujo de Tokens -->
            <div class="modal-info-box" style="border-left: 3px solid var(--primary-cyan);">
                <strong style="color: var(--primary-cyan);">🪙 Activo & Flujo de Tokens:</strong>
                <div style="margin-top: 6px; font-size: 13px;">
                    Token Origen: <span class="badge-token"><span class="token-symbol">${ev.token_origen || 'BTC (Nativo)'}</span></span>
                    &nbsp;➔&nbsp;
                    Token Destino: <span class="badge-token"><span class="token-symbol">${ev.token_destino || 'BTC (Nativo)'}</span></span>
                </div>
                <div style="margin-top: 6px; font-size: 11px; color: var(--text-muted);">
                    ${ev.nota_tokens || 'Transacción en la Capa 1 de Bitcoin (UTXO). Las entradas a exchanges ingresan a los libros de órdenes spot para su potencial conversión.'}
                </div>
            </div>

            <!-- 2. Señales de Impacto en el Precio de Bitcoin -->
            <div class="modal-info-box" style="border-left: 3px solid #38bdf8;">
                <strong style="color: #38bdf8;">📊 Señales de Impacto en el Precio de BTC (Estimación Probabilística):</strong>
                
                <div class="senales-modal-grid">
                    <!-- Corto Plazo 24h -->
                    <div class="senal-modal-card ${s24.direccion || 'NEUTRAL'}">
                        <div style="font-size: 11px; color: var(--text-dim); font-weight: 600;">⚡ CORTO PLAZO (24H)</div>
                        <div style="margin: 6px 0;">
                            <span class="badge-signal ${s24.direccion || 'NEUTRAL'}">
                                ${s24.direccion === 'ALCISTA' ? '▲ ALCISTA' : s24.direccion === 'BAJISTA' ? '▼ BAJISTA' : '■ NEUTRAL'}
                                ${s24.retorno_esperado_pct !== undefined ? (s24.retorno_esperado_pct > 0 ? '+' : '') + s24.retorno_esperado_pct.toFixed(2) + '%' : ''}
                            </span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                            Probabilidad: <strong>${((s24.probabilidad_principal || 0.6) * 100).toFixed(0)}%</strong>
                        </div>
                        <div style="font-size: 10px; color: var(--text-dim); line-height: 1.3;">
                            ${s24.interpretacion || 'Impacto evaluado sobre la liquidez y profundidad spot.'}
                        </div>
                    </div>

                    <!-- Mediano Plazo 7d -->
                    <div class="senal-modal-card ${s7.direccion || 'NEUTRAL'}">
                        <div style="font-size: 11px; color: var(--text-dim); font-weight: 600;">📈 MEDIANO PLAZO (7D)</div>
                        <div style="margin: 6px 0;">
                            <span class="badge-signal ${s7.direccion || 'NEUTRAL'}">
                                ${s7.direccion === 'ALCISTA' ? '▲ ALCISTA' : s7.direccion === 'BAJISTA' ? '▼ BAJISTA' : '■ NEUTRAL'}
                                ${s7.retorno_esperado_pct !== undefined ? (s7.retorno_esperado_pct > 0 ? '+' : '') + s7.retorno_esperado_pct.toFixed(2) + '%' : ''}
                            </span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                            Probabilidad: <strong>${((s7.probabilidad_principal || 0.5) * 100).toFixed(0)}%</strong>
                        </div>
                        <div style="font-size: 10px; color: var(--text-dim); line-height: 1.3;">
                            ${s7.interpretacion || 'Absorción o acumulación durante el ciclo semanal.'}
                        </div>
                    </div>

                    <!-- Largo Plazo 30d -->
                    <div class="senal-modal-card ${s30.direccion || 'NEUTRAL'}">
                        <div style="font-size: 11px; color: var(--text-dim); font-weight: 600;">🔭 LARGO PLAZO (30D)</div>
                        <div style="margin: 6px 0;">
                            <span class="badge-signal ${s30.direccion || 'NEUTRAL'}">
                                ${s30.direccion === 'ALCISTA' ? '▲ ALCISTA' : s30.direccion === 'BAJISTA' ? '▼ BAJISTA' : '■ NEUTRAL'}
                                ${s30.retorno_esperado_pct !== undefined ? (s30.retorno_esperado_pct > 0 ? '+' : '') + s30.retorno_esperado_pct.toFixed(2) + '%' : ''}
                            </span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                            Probabilidad: <strong>${((s30.probabilidad_principal || 0.5) * 100).toFixed(0)}%</strong>
                        </div>
                        <div style="font-size: 10px; color: var(--text-dim); line-height: 1.3;">
                            ${s30.interpretacion || 'Dinámica estructural de reservas a largo plazo.'}
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3. Participantes y Direcciones -->
            <div class="modal-info-box">
                <strong>🏛️ Entidades & Billeteras:</strong>
                <div style="margin-top: 4px;">Origen: <strong>${ev.entidad_origen}</strong></div>
                ${dirInHtml}
                <div style="margin-top: 8px;">Destino: <strong>${ev.entidad_destino}</strong></div>
                ${dirOutHtml}
                <div style="margin-top: 8px; font-size: 11px; color: var(--text-dim);">
                    Confianza de atribución: <strong>${(ev.nivel_confianza * 100).toFixed(1)}%</strong> &bull;
                    Rastreado con: <strong>ChainQuery Top 100 Rich List & BTCScan Explorer</strong>
                </div>
            </div>

            <!-- 4. Transacción On-Chain -->
            <div class="modal-info-box">
                <strong>⛓️ Transacción On-Chain (TxID):</strong>
                <div style="word-break: break-all; font-family: var(--font-mono); font-size: 11px; margin-top: 4px;">
                    ${ev.txid}
                </div>
                <div style="margin-top: 6px; display: flex; gap: 12px; font-size: 12px;">
                    <a href="${enlaceBtcscanTx}" target="_blank" style="color: var(--primary-cyan);">Abrir en BTCScan.org ↗</a>
                    <a href="${enlaceMempoolTx}" target="_blank" style="color: var(--primary-cyan);">Abrir en Mempool.space ↗</a>
                    <a href="https://chainquery.com/lists/rich-list" target="_blank" style="color: #f59e0b;">Consultar Rich List ↗</a>
                </div>
            </div>

            <!-- 5. Evidencia y Limitaciones -->
            <div class="modal-info-box">
                <strong>📜 Evidencia On-Chain:</strong>
                <p style="margin-top: 4px; color: var(--text-muted); font-size: 12px;">${ev.evidencia}</p>
            </div>

            <div class="modal-info-box" style="border-left: 3px solid var(--accent-amber);">
                <strong style="color: var(--accent-amber);">⚖️ Limitaciones Epistémicas (Principio IV):</strong>
                <p style="margin-top: 4px; color: var(--text-muted); font-size: 12px;">${ev.limitaciones}</p>
                <div style="margin-top: 6px; font-size: 11px; color: #fbbf24; font-style: italic;">
                    Ninguna transferencia se interpreta como orden de compra o venta ejecutada. Toda señal representa un estimador probabilístico de impacto potencial sobre la liquidez.
                </div>
            </div>
        `;
    }

    const modal = document.getElementById("modal-detalle");
    if (modal) modal.classList.add("active");
}

function cerrarModal(e) {
    const modal = document.getElementById("modal-detalle");
    if (modal) modal.classList.remove("active");
}

async function ejecutarCicloOnDemand() {
    const btn = document.getElementById("btn-sync");
    const btnText = btn ? btn.querySelector(".btn-text") : null;
    const btnIcon = btn ? btn.querySelector(".btn-icon") : null;

    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = "Sincronizando On-Chain...";
    if (btnIcon) btnIcon.textContent = "⏳";

    try {
        const resp = await fetch("/api/ejecutar-ciclo", { method: "POST" });
        const data = await resp.json();

        if (data.exito) {
            await cargarResumen();
            await cargarEventos(false);
            await cargarPredicciones();
            alert("✅ Ciclo de monitoreo completado exitosamente: datos de mercado sincronizados y bloques examinados.");
        } else {
            alert(`⚠️ Error durante el ciclo: ${data.error || "Falla desconocida"}`);
        }
    } catch (err) {
        alert("Error de comunicación con el servidor local.");
    } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = "Ejecutar Monitoreo";
        if (btnIcon) btnIcon.textContent = "⚡";
    }
}
