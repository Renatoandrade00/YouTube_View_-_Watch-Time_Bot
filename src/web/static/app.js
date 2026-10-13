// YouTube Watch-Time Bot — Dashboard Controller
document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const urlsInput = document.getElementById("urls-input");
    const urlsCountBadge = document.getElementById("urls-count-badge");
    const btnLoadDefaults = document.getElementById("btn-load-defaults");
    const btnExtractPlaylist = document.getElementById("btn-extract-playlist");

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
    const togglePersistentProfiles = document.getElementById("toggle-persistent-profiles");
    const cookiesFileInput = document.getElementById("cookies-file-input");
    const toggleHeadless = document.getElementById("toggle-headless");
    const toggleMute = document.getElementById("toggle-mute");
    const toggleBlockMedia = document.getElementById("toggle-block-media");
    const toggleAutoRecovery = document.getElementById("toggle-auto-recovery");
    const toggleSearchPlay = document.getElementById("toggle-search-play");

    // Proxy DOM Elements
    const toggleEnableProxy = document.getElementById("toggle-enable-proxy");
    const proxyDetailsContainer = document.getElementById("proxy-details-container");
    const proxiesInput = document.getElementById("proxies-input");
    const proxiesCountBadge = document.getElementById("proxies-count-badge");
    const btnLoadProxies = document.getElementById("btn-load-proxies");
    const proxyTemplateInput = document.getElementById("proxy-template-input");
    const toggleProxyLowBw = document.getElementById("toggle-proxy-low-bw");

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

    // Abas e Histórico DOM Elements
    const tabLiveBtn = document.getElementById("tab-live-btn");
    const tabHistoryBtn = document.getElementById("tab-history-btn");
    const historyCountBadge = document.getElementById("history-count-badge");
    const viewLive = document.getElementById("view-live");
    const viewHistory = document.getElementById("view-history");

    const histTotalRuns = document.getElementById("hist-total-runs");
    const histTotalHours = document.getElementById("hist-total-hours");
    const histTotalViews = document.getElementById("hist-total-views");
    const histSuccessRate = document.getElementById("hist-success-rate");
    const histAdsSkipped = document.getElementById("hist-ads-skipped");

    const btnRefreshHistory = document.getElementById("btn-refresh-history");
    const btnClearHistory = document.getElementById("btn-clear-history");
    const historyTableBody = document.getElementById("history-table-body");
    const emptyHistoryMsg = document.getElementById("empty-history-msg");

    const runDetailsModal = document.getElementById("run-details-modal");
    const modalRunTitle = document.getElementById("modal-run-title");
    const modalRunStatus = document.getElementById("modal-run-status");
    const modalMetaGrid = document.getElementById("modal-meta-grid");
    const modalSessionsBody = document.getElementById("modal-sessions-body");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnModalCloseFooter = document.getElementById("btn-modal-close-footer");

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

    // Extrair vídeos de Playlist ou Canal
    if (btnExtractPlaylist) {
        btnExtractPlaylist.addEventListener("click", async () => {
            const rawText = urlsInput.value.trim();
            if (!rawText) {
                showToast("Insira ao menos um link de playlist, canal ou vídeo para extrair.", "warning");
                return;
            }

            const lines = rawText.split("\n").map(l => l.trim()).filter(l => l.length > 0);
            const originalBtnText = btnExtractPlaylist.textContent;
            btnExtractPlaylist.disabled = true;
            btnExtractPlaylist.textContent = "⏳ Extraindo...";

            try {
                showToast("Buscando e processando vídeos do YouTube...", "info");
                const res = await fetch("/api/extract-videos", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ urls: lines })
                });

                const data = await res.json();
                if (!res.ok) {
                    showToast(data.detail || "Erro ao extrair vídeos.", "error");
                    return;
                }

                if (data.videos && data.videos.length > 0) {
                    urlsInput.value = data.videos.join("\n");
                    updateUrlsCount();
                    showToast(`✨ Sucesso! ${data.count} vídeos carregados na lista.`, "success");
                } else {
                    showToast("Nenhum vídeo pôde ser extraído dos links fornecidos.", "warning");
                }
            } catch (err) {
                console.error("Erro na extração:", err);
                showToast("Falha na comunicação com o servidor ao extrair vídeos.", "error");
            } finally {
                btnExtractPlaylist.disabled = false;
                btnExtractPlaylist.textContent = originalBtnText;
            }
        });
    }

    // Controles de Proxy
    if (toggleEnableProxy) {
        toggleEnableProxy.addEventListener("change", (e) => {
            if (proxyDetailsContainer) {
                proxyDetailsContainer.style.display = e.target.checked ? "block" : "none";
            }
        });
    }

    function updateProxiesCount() {
        if (!proxiesInput || !proxiesCountBadge) return [];
        const text = proxiesInput.value.trim();
        if (!text) {
            proxiesCountBadge.textContent = "0 proxies";
            return [];
        }
        const lines = text.split("\n")
            .map(l => l.trim())
            .filter(l => l.length > 0 && !l.startsWith("#"));
        proxiesCountBadge.textContent = `${lines.length} prox${lines.length === 1 ? 'y' : 'ies'}`;
        return lines;
    }

    if (proxiesInput) {
        proxiesInput.addEventListener("input", updateProxiesCount);
    }

    if (btnLoadProxies) {
        btnLoadProxies.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/default-proxies");
                const data = await res.json();
                if (data.proxies && data.proxies.length > 0) {
                    proxiesInput.value = data.proxies.join("\n");
                    updateProxiesCount();
                    showToast(`Carregados ${data.proxies.length} proxies de proxies.txt`, "success");
                } else {
                    showToast("Arquivo proxies.txt vazio ou não encontrado.", "warn");
                }
            } catch (err) {
                console.error("Falha ao carregar proxies.txt:", err);
            }
        });
    }


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
        const wasRunning = isRunning;
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
            if (wasRunning) {
                setTimeout(loadHistory, 1200);
            }
        }
    }

    // Determina a classe CSS adequada para o badge de status
    function getStatusClass(status) {
        if (!status) return "Aguardando";
        if (status.includes("Assistindo")) return "Assistindo";
        if (status.includes("Buscando") || status.includes("Search")) return "Buscando";
        if (status.includes("Recuperando")) return "Recuperando";
        if (status.includes("Novo IP")) return "NovoIP";
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
                    <span class="worker-proxy" title="${w.proxy_info || 'Conexão Direta'}">🌐 ${w.proxy_info || 'Local'}</span>
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

            const proxyEl = card.querySelector(".worker-proxy");
            if (proxyEl && w.proxy_info) {
                proxyEl.textContent = `🌐 ${w.proxy_info}`;
                proxyEl.title = w.proxy_info;
            }
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
            enable_proxy: toggleEnableProxy ? toggleEnableProxy.checked : false,
            proxies: updateProxiesCount(),
            proxy_session_template: (proxyTemplateInput && proxyTemplateInput.value.trim()) ? proxyTemplateInput.value.trim() : null,
            proxy_low_bandwidth: toggleProxyLowBw ? toggleProxyLowBw.checked : true,
            use_persistent_profiles: togglePersistentProfiles ? togglePersistentProfiles.checked : false,
            cookies_file: (cookiesFileInput && cookiesFileInput.value.trim()) ? cookiesFileInput.value.trim() : null,
            block_heavy_media: toggleBlockMedia ? toggleBlockMedia.checked : true,
            auto_player_recovery: toggleAutoRecovery ? toggleAutoRecovery.checked : true,
            search_and_play: toggleSearchPlay ? toggleSearchPlay.checked : false,
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

    // ==========================================
    // MÓDULO DE HISTÓRICO & PERSISTÊNCIA (SQLite)
    // ==========================================

    // Alternância de Abas (Painel ao Vivo vs Histórico)
    function switchTab(tab) {
        if (tab === "history") {
            if (tabHistoryBtn) tabHistoryBtn.classList.add("active");
            if (tabLiveBtn) tabLiveBtn.classList.remove("active");
            if (viewLive) viewLive.style.display = "none";
            if (viewHistory) viewHistory.style.display = "block";
            loadHistory();
        } else {
            if (tabLiveBtn) tabLiveBtn.classList.add("active");
            if (tabHistoryBtn) tabHistoryBtn.classList.remove("active");
            if (viewHistory) viewHistory.style.display = "none";
            if (viewLive) viewLive.style.display = "block";
        }
    }

    if (tabLiveBtn) tabLiveBtn.addEventListener("click", () => switchTab("live"));
    if (tabHistoryBtn) tabHistoryBtn.addEventListener("click", () => switchTab("history"));

    function formatDuration(sec) {
        if (!sec || sec <= 0) return "0s";
        const m = Math.floor(sec / 60);
        const s = Math.round(sec % 60);
        if (m === 0) return `${s}s`;
        const h = Math.floor(m / 60);
        const remM = m % 60;
        if (h === 0) return `${m}m ${s}s`;
        return `${h}h ${remM}m`;
    }

    // Carregar dados de histórico da API SQLite
    async function loadHistory() {
        try {
            const res = await fetch("/api/history");
            if (!res.ok) throw new Error("Erro ao consultar histórico");
            const data = await res.json();
            const runs = data.runs || [];
            const stats = data.stats || {};

            // Atualiza badge de contagem
            if (historyCountBadge) historyCountBadge.textContent = runs.length;

            // Atualiza KPI cards
            if (histTotalRuns) histTotalRuns.textContent = stats.total_runs || 0;
            if (histTotalHours) histTotalHours.textContent = `${stats.total_watch_hours || 0}h`;
            if (histTotalViews) histTotalViews.textContent = stats.total_views || 0;
            if (histSuccessRate) histSuccessRate.textContent = `${stats.success_rate || 100}%`;
            if (histAdsSkipped) histAdsSkipped.textContent = (stats.total_ads_skipped || 0) + (stats.total_continue_clicked || 0);

            // Renderiza tabela
            if (!historyTableBody) return;
            historyTableBody.innerHTML = "";

            if (runs.length === 0) {
                if (emptyHistoryMsg) emptyHistoryMsg.style.display = "block";
                return;
            }
            if (emptyHistoryMsg) emptyHistoryMsg.style.display = "none";

            runs.forEach(run => {
                const tr = document.createElement("tr");
                const statusClass = (run.status || "COMPLETED").toLowerCase();
                const watchMins = (run.actual_watch_time / 60).toFixed(1);
                tr.innerHTML = `
                    <td><strong>#${run.id}</strong></td>
                    <td>${run.started_at || '—'}</td>
                    <td>${formatDuration(run.duration_seconds)}</td>
                    <td>${run.workers}</td>
                    <td>${run.urls_count} vídeos</td>
                    <td>${run.successful_views} / ${run.total_views}</td>
                    <td><strong>${watchMins} min</strong></td>
                    <td><span class="badge-status ${statusClass}">${run.status}</span></td>
                    <td>
                        <div class="table-row-actions">
                            <button type="button" class="btn-xs btn-subtle btn-details" data-id="${run.id}">🔍 Detalhes</button>
                            <button type="button" class="btn-xs btn-danger-subtle btn-del-run" data-id="${run.id}" title="Excluir rodada">🗑️</button>
                        </div>
                    </td>
                `;
                historyTableBody.appendChild(tr);
            });

            // Adiciona listeners para botões de detalhes e exclusão
            historyTableBody.querySelectorAll(".btn-details").forEach(btn => {
                btn.addEventListener("click", () => {
                    const runId = btn.getAttribute("data-id");
                    openRunDetails(runId);
                });
            });

            historyTableBody.querySelectorAll(".btn-del-run").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const runId = btn.getAttribute("data-id");
                    if (confirm(`Tem certeza que deseja excluir o registro da Rodada #${runId}?`)) {
                        await deleteRun(runId);
                    }
                });
            });

        } catch (err) {
            console.error("Erro ao carregar histórico:", err);
            showToast("Falha ao carregar registros do histórico.", "error");
        }
    }

    // Excluir rodada individual
    async function deleteRun(runId) {
        try {
            const res = await fetch(`/api/history/${runId}`, { method: "DELETE" });
            if (res.ok) {
                showToast(`Rodada #${runId} excluída com sucesso.`, "info");
                loadHistory();
            } else {
                showToast("Erro ao excluir rodada.", "error");
            }
        } catch (err) {
            showToast("Falha na comunicação ao excluir rodada.", "error");
        }
    }

    // Limpar todo o histórico
    if (btnClearHistory) {
        btnClearHistory.addEventListener("click", async () => {
            if (confirm("ATENÇÃO: Deseja realmente excluir TODO o histórico de execuções armazenado? Esta ação não pode ser desfeita.")) {
                try {
                    const res = await fetch("/api/history", { method: "DELETE" });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(`Histórico completamente limpo (${data.deleted_count || 0} rodadas removidas).`, "info");
                        loadHistory();
                    } else {
                        showToast("Erro ao limpar histórico.", "error");
                    }
                } catch (err) {
                    showToast("Falha ao comunicar com o servidor.", "error");
                }
            }
        });
    }

    if (btnRefreshHistory) {
        btnRefreshHistory.addEventListener("click", () => {
            loadHistory();
            showToast("Histórico atualizado.", "info");
        });
    }

    // Modal de detalhes da rodada
    async function openRunDetails(runId) {
        try {
            const res = await fetch(`/api/history/${runId}`);
            if (!res.ok) throw new Error("Rodada não encontrada");
            const run = await res.json();

            if (modalRunTitle) modalRunTitle.textContent = `Detalhes da Rodada #${run.id}`;
            const statusClass = (run.status || "COMPLETED").toLowerCase();
            if (modalRunStatus) {
                modalRunStatus.textContent = run.status;
                modalRunStatus.className = `badge-status ${statusClass}`;
            }

            const watchMins = (run.actual_watch_time / 60).toFixed(1);
            if (modalMetaGrid) {
                modalMetaGrid.innerHTML = `
                    <div class="modal-meta-item">
                        <span class="label">Início</span>
                        <span class="value">${run.started_at || '—'}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Término</span>
                        <span class="value">${run.finished_at || '—'}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Duração Real</span>
                        <span class="value">${formatDuration(run.duration_seconds)}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Workers</span>
                        <span class="value">${run.workers}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Vídeos Alvo</span>
                        <span class="value">${run.urls_count}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Watch Time</span>
                        <span class="value">${watchMins} min</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Sessões OK</span>
                        <span class="value">${run.successful_views} / ${run.total_views}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Bloqueios / Falhas</span>
                        <span class="value">${run.blocked_views} / ${run.failed_views}</span>
                    </div>
                    <div class="modal-meta-item">
                        <span class="label">Popups / Ads</span>
                        <span class="value">${(run.ads_skipped || 0) + (run.continue_clicked || 0)}</span>
                    </div>
                `;
            }

            if (modalSessionsBody) {
                modalSessionsBody.innerHTML = "";
                const sessions = run.sessions || [];
                if (sessions.length === 0) {
                    modalSessionsBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhuma sessão individual registrada nesta rodada.</td></tr>`;
                } else {
                    sessions.forEach(s => {
                        const tr = document.createElement("tr");
                        const sClass = (s.status || "SUCCESS").toLowerCase();
                        const sWatch = (s.actual_watch_time || 0).toFixed(1);
                        const sTarget = (s.target_watch_time || 0).toFixed(0);
                        tr.innerHTML = `
                            <td><strong>#${s.session_id || s.id}</strong></td>
                            <td>Worker ${s.worker_id || 1}</td>
                            <td class="url-cell" title="${s.url || ''}"><a href="${s.url}" target="_blank" style="color:var(--primary);text-decoration:none;">${s.url || '—'}</a></td>
                            <td><strong>${sWatch}s</strong> / ${sTarget}s</td>
                            <td>Ads: ${s.ads_skipped || 0} | Popups: ${s.continue_clicked || 0}</td>
                            <td><span class="badge-status ${sClass}">${s.status}</span></td>
                            <td>${s.error_message ? `<span style="color:var(--danger);font-size:0.75rem;" title="${s.error_message}">${s.error_message.substring(0, 35)}...</span>` : '<span style="color:var(--success);">OK</span>'}</td>
                        `;
                        modalSessionsBody.appendChild(tr);
                    });
                }
            }

            if (runDetailsModal) runDetailsModal.style.display = "flex";
        } catch (err) {
            console.error("Erro ao carregar detalhes:", err);
            showToast("Falha ao abrir detalhes da rodada.", "error");
        }
    }

    function closeModal() {
        if (runDetailsModal) runDetailsModal.style.display = "none";
    }

    if (btnCloseModal) btnCloseModal.addEventListener("click", closeModal);
    if (btnModalCloseFooter) btnModalCloseFooter.addEventListener("click", closeModal);
    if (runDetailsModal) {
        runDetailsModal.addEventListener("click", (e) => {
            if (e.target === runDetailsModal) closeModal();
        });
    }

    // Inicialização
    loadDefaultUrls();
    loadHistory();
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

