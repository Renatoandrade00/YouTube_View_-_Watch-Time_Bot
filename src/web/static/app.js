// YouTube Watch-Time Bot — Dashboard Controller
document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const urlsInput = document.getElementById("urls-input");
    const urlsCountBadge = document.getElementById("urls-count-badge");
    const btnLoadDefaults = document.getElementById("btn-load-defaults");

    const workersSlider = document.getElementById("workers-slider");
    const workersVal = document.getElementById("workers-val");

    const durationSlider = document.getElementById("duration-slider");
    const durationVal = document.getElementById("duration-val");

    const minWatchInput = document.getElementById("min-watch-input");
    const maxWatchInput = document.getElementById("max-watch-input");
    const minDelayInput = document.getElementById("min-delay-input");
    const maxDelayInput = document.getElementById("max-delay-input");
    const staggerDelayInput = document.getElementById("stagger-delay-input");

    const toggleAntiFingerprint = document.getElementById("toggle-anti-fingerprint");
    const toggleMicroInteractions = document.getElementById("toggle-micro-interactions");
    const toggleSkipAds = document.getElementById("toggle-skip-ads");
    const toggleAutoContinue = document.getElementById("toggle-auto-continue");
    const toggleHeadless = document.getElementById("toggle-headless");
    const toggleMute = document.getElementById("toggle-mute");

    const btnStart = document.getElementById("btn-start");
    const btnStop = document.getElementById("btn-stop");

    const connectionDot = document.getElementById("connection-dot");
    const connectionStatusText = document.getElementById("connection-status-text");
    const runtimeVal = document.getElementById("runtime-val");

    const metricWatchTime = document.getElementById("metric-watch-time");
    const metricSessions = document.getElementById("metric-sessions");
    const metricPopups = document.getElementById("metric-popups");
    const metricWorkersActive = document.getElementById("metric-workers-active");

    const botMainBadge = document.getElementById("bot-main-badge");
    const workersContainer = document.getElementById("workers-container");
    const emptyWorkersMsg = document.getElementById("empty-workers-msg");

    const terminalLogs = document.getElementById("terminal-logs");
    const toggleAutoscroll = document.getElementById("toggle-autoscroll");
    const btnClearLogs = document.getElementById("btn-clear-logs");
    const toastContainer = document.getElementById("toast-container");

    let isRunning = false;
    let ws = null;
    let wsReconnectTimer = null;
    let workerElements = new Map();

    // Sincronização dos Sliders
    workersSlider.addEventListener("input", (e) => {
        workersVal.textContent = e.target.value;
    });

    durationSlider.addEventListener("input", (e) => {
        durationVal.textContent = `${parseFloat(e.target.value).toFixed(1)}h`;
    });

    // Contagem de URLs
    function updateUrlsCount() {
        const text = urlsInput.value.trim();
        if (!text) {
            urlsCountBadge.textContent = "0 vídeos";
            return [];
        }
        const lines = text.split("\n")
            .map(l => l.trim())
            .filter(l => l.length > 0 && l.startsWith("http"));
        urlsCountBadge.textContent = `${lines.length} vídeo${lines.length === 1 ? '' : 's'}`;
        return lines;
    }

    urlsInput.addEventListener("input", updateUrlsCount);

    // Carregar URLs padrão
    async function loadDefaultUrls() {
        try {
            const res = await fetch("/api/default-urls");
            const data = await res.json();
            if (data.urls && data.urls.length > 0) {
                urlsInput.value = data.urls.join("\n");
                updateUrlsCount();
                showToast(`Carregados ${data.urls.length} vídeos de urls.txt`, "success");
            }
        } catch (err) {
            console.error("Falha ao carregar urls.txt:", err);
        }
    }

    btnLoadDefaults.addEventListener("click", loadDefaultUrls);

    // Toast Notifications
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // Terminal Logger
    function appendTerminalLog(logLine) {
        const el = document.createElement("div");
        el.className = "log-line";
        if (logLine.includes("[ERROR]")) el.classList.add("error");
        else if (logLine.includes("[WARNING]")) el.classList.add("warn");
        else el.classList.add("info");

        el.textContent = logLine;
        terminalLogs.appendChild(el);

        if (toggleAutoscroll.checked) {
            terminalLogs.scrollTop = terminalLogs.scrollHeight;
        }

        // Limita nós para evitar vazamento de memória
        while (terminalLogs.children.length > 400) {
            terminalLogs.removeChild(terminalLogs.firstChild);
        }
    }

    btnClearLogs.addEventListener("click", () => {
        terminalLogs.innerHTML = "";
    });

    // Formatação de Segundos para H:M:S
    function formatSeconds(totalSec) {
        const sec = Math.floor(totalSec || 0);
        const hours = Math.floor(sec / 3600);
        const minutes = Math.floor((sec % 3600) / 60);
        return `${hours}h ${minutes.toString().padStart(2, "0")}m`;
    }

    // Atualização de UI conforme estado de execução
    function setRunningState(running) {
        isRunning = running;
        btnStart.disabled = running;
        btnStop.disabled = !running;

        if (running) {
            botMainBadge.textContent = "Em Execução";
            botMainBadge.className = "badge-status running";
            if (emptyWorkersMsg) emptyWorkersMsg.style.display = "none";
        } else {
            botMainBadge.textContent = "Parado";
            botMainBadge.className = "badge-status";
        }
    }

    // Determina a classe CSS adequada para o badge de status
    function getStatusClass(status) {
        if (!status) return "Aguardando";
        if (status.includes("Assistindo")) return "Assistindo";
        if (status.includes("Navegando")) return "Navegando";
        if (status.includes("Inicia em") || status.includes("Aguardando")) return "Escalonando";
        if (status.includes("Bloqueio") || status.includes("CAPTCHA")) return "Bloqueado";
        if (status.includes("Pausa")) return "Pausa";
        if (status.includes("Reiniciando")) return "Reiniciando";
        if (status.includes("Finalizado") || status.includes("Concluído")) return "Finalizado";
        return "Aguardando";
    }

    // Atualização ou Criação de Card de Worker
    function updateWorkerCard(w) {
        if (!w || !w.worker_id) return;
        const wid = w.worker_id;

        if (emptyWorkersMsg) emptyWorkersMsg.style.display = "none";

        const statusClass = getStatusClass(w.status);

        let card = workerElements.get(wid);
        if (!card) {
            card = document.createElement("div");
            card.className = "worker-card";
            card.id = `worker-card-${wid}`;
            card.innerHTML = `
                <div class="worker-top-row">
                    <span class="worker-id-badge">Worker #${wid}</span>
                    <span class="worker-status-pill ${statusClass}">${w.status || 'Aguardando'}</span>
                </div>
                <div class="worker-url" title="${w.current_url || 'Nenhum vídeo'}">
                    ${w.current_url ? `<a href="${w.current_url}" target="_blank">🔗 ${w.current_url.substring(0, 36)}...</a>` : 'Aguardando próximo vídeo...'}
                </div>
                <div class="worker-progress-wrap">
                    <div class="progress-track">
                        <div class="progress-bar" style="width: ${w.progress_pct || 0}%"></div>
                    </div>
                    <div class="progress-info">
                        <span class="progress-time">${((w.current_watch_time || 0) / 60).toFixed(1)} min / ${((w.target_watch_time || 0) / 60).toFixed(1)} min</span>
                        <span class="progress-pct">${w.progress_pct || 0}%</span>
                    </div>
                </div>
                <div class="worker-footer">
                    <span class="worker-gpu" title="GPU Simulada">🎮 ${w.gpu_info || 'GPU Padrão'}</span>
                    <span class="worker-ads">🎯 Ads: ${w.ads_skipped || 0}</span>
                </div>
            `;
            workersContainer.appendChild(card);
            workerElements.set(wid, card);
        } else {
            // Atualização pontual e rápida dos elementos
            const statusPill = card.querySelector(".worker-status-pill");
            if (statusPill) {
                statusPill.textContent = w.status || "Aguardando";
                statusPill.className = `worker-status-pill ${statusClass}`;
            }

            const urlEl = card.querySelector(".worker-url");
            if (urlEl && w.current_url) {
                urlEl.innerHTML = `<a href="${w.current_url}" target="_blank">🔗 ${w.current_url.substring(0, 36)}...</a>`;
                urlEl.title = w.current_url;
            }

            const bar = card.querySelector(".progress-bar");
            if (bar) bar.style.width = `${w.progress_pct || 0}%`;

            const timeEl = card.querySelector(".progress-time");
            if (timeEl) {
                timeEl.textContent = `${((w.current_watch_time || 0) / 60).toFixed(1)} min / ${((w.target_watch_time || 0) / 60).toFixed(1)} min`;
            }

            const pctEl = card.querySelector(".progress-pct");
            if (pctEl) pctEl.textContent = `${w.progress_pct || 0}%`;

            const adsEl = card.querySelector(".worker-ads");
            if (adsEl) adsEl.textContent = `🎯 Ads: ${w.ads_skipped || 0}`;

            const gpuEl = card.querySelector(".worker-gpu");
            if (gpuEl && w.gpu_info) gpuEl.textContent = `🎮 ${w.gpu_info}`;
        }
    }

    // Atualização de Métricas Globais
    function updateMetrics(metrics) {
        if (!metrics) return;
        metricWatchTime.textContent = formatSeconds(metrics.total_watch_seconds);
        metricSessions.textContent = `${metrics.successful_sessions || 0} / ${metrics.total_sessions || 0}`;
        metricPopups.textContent = (metrics.total_continue_clicked || 0).toString();
    }

    // Inicialização do WebSocket
    function connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/live`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            connectionDot.className = "pulse-dot online";
            connectionStatusText.textContent = "Conectado";
            if (wsReconnectTimer) {
                clearInterval(wsReconnectTimer);
                wsReconnectTimer = null;
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === "INITIAL_STATE") {
                    const d = msg.data;
                    setRunningState(d.is_running);
                    runtimeVal.textContent = d.elapsed_time || "00:00:00";
                    updateMetrics(d.metrics);
                    if (d.workers && d.workers.length > 0) {
                        d.workers.forEach(w => updateWorkerCard(w));
                        const activeCount = d.workers.filter(w => w.status && w.status !== "Finalizado" && w.status !== "Aguardando" && w.status !== "Falha").length;
                        metricWorkersActive.textContent = `${activeCount} / ${d.workers.length}`;
                    }
                    if (d.recent_logs && d.recent_logs.length > 0) {
                        terminalLogs.innerHTML = "";
                        d.recent_logs.forEach(l => appendTerminalLog(l));
                    }
                } else if (msg.type === "WORKER_UPDATE") {
                    updateWorkerCard(msg.data);
                    const activeCount = Array.from(workerElements.values()).filter(c => {
                        const s = c.querySelector(".worker-status-pill");
                        const txt = s ? s.textContent : "";
                        return txt && txt !== "Finalizado" && txt !== "Aguardando" && txt !== "Falha";
                    }).length;
                    metricWorkersActive.textContent = `${activeCount} / ${workerElements.size}`;
                } else if (msg.type === "METRICS_UPDATE") {
                    updateMetrics(msg.data);
                } else if (msg.type === "LOG_ENTRY") {
                    appendTerminalLog(msg.data);
                }
            } catch (err) {
                console.error("Erro ao processar mensagem WebSocket:", err);
            }
        };

        ws.onclose = () => {
            connectionDot.className = "pulse-dot offline";
            connectionStatusText.textContent = "Desconectado (Reconectando...)";
            if (!wsReconnectTimer) {
                wsReconnectTimer = setTimeout(connectWebSocket, 2500);
            }
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    // Iniciar Bot
    btnStart.addEventListener("click", async () => {
        const urls = updateUrlsCount();
        if (urls.length === 0) {
            showToast("Insira ao menos uma URL válida do YouTube!", "error");
            urlsInput.focus();
            return;
        }

        const minWatchMin = parseFloat(minWatchInput.value) || 2.0;
        const maxWatchMin = parseFloat(maxWatchInput.value) || 5.0;

        const payload = {
            urls: urls,
            workers: parseInt(workersSlider.value, 10),
            duration_hours: parseFloat(durationSlider.value),
            continuous: true,
            min_watch_minutes: minWatchMin,
            max_watch_minutes: maxWatchMin,
            min_watch: minWatchMin,
            max_watch: maxWatchMin,
            min_delay: parseFloat(minDelayInput.value),
            max_delay: parseFloat(maxDelayInput.value),
            stagger_delay: parseFloat(staggerDelayInput ? staggerDelayInput.value : 15) || 15.0,
            headless: toggleHeadless.checked,
            mute: toggleMute.checked,
            anti_fingerprint: toggleAntiFingerprint.checked,
            micro_interactions: toggleMicroInteractions.checked,
            skip_ads: toggleSkipAds.checked,
            auto_continue: toggleAutoContinue.checked,
        };

        try {
            btnStart.disabled = true;
            const res = await fetch("/api/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok) {
                showToast("🚀 Bot iniciado com sucesso!", "success");
                setRunningState(true);
                // Prepara container de workers
                workersContainer.innerHTML = "";
                workerElements.clear();
                for (let i = 1; i <= payload.workers; i++) {
                    updateWorkerCard({ worker_id: i, status: "Iniciando...", current_watch_time: 0, target_watch_time: 0 });
                }
                metricWorkersActive.textContent = `0 / ${payload.workers}`;
            } else {
                showToast(`Erro: ${data.detail || "Falha ao iniciar"}`, "error");
                btnStart.disabled = false;
            }
        } catch (err) {
            showToast("Falha na comunicação com o servidor.", "error");
            btnStart.disabled = false;
        }
    });

    // Parar Bot
    btnStop.addEventListener("click", async () => {
        try {
            btnStop.disabled = true;
            const res = await fetch("/api/stop", { method: "POST" });
            const data = await res.json();
            showToast("🛑 Parada solicitada para todos os workers.", "info");
            setRunningState(false);
        } catch (err) {
            showToast("Falha ao enviar sinal de parada.", "error");
            btnStop.disabled = false;
        }
    });

    // Inicialização
    loadDefaultUrls();
    connectWebSocket();

    // Heartbeat / Atualização de tempo decorrido a cada 1s
    setInterval(async () => {
        if (isRunning) {
            try {
                const res = await fetch("/api/status");
                const data = await res.json();
                runtimeVal.textContent = data.elapsed_time || "00:00:00";
                if (!data.is_running && isRunning) {
                    setRunningState(false);
                    showToast("Duração Total da Rodada concluída. Workers encerrados.", "info");
                }
            } catch (e) {
                // silencioso
            }
        }
    }, 1000);
});
