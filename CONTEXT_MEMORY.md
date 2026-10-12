# Memória de Contexto do Projeto: YouTube View & Watch-Time Bot

> **Data de Atualização:** Outubro de 2026  
> **Versão do Projeto:** 2.4 (Search & Play Orgânico + Ultra-Light + Auto Player Recovery + SQLite + Session Profiles)  
> **Status dos Testes:** 63/63 testes passando (100% de sucesso)  
> **Repositório:** `Renatoandrade00/YouTube_View_-_Watch-Time_Bot`

---

## 1. Visão Geral e Propósito

O **YouTube View & Watch-Time Bot** é um sistema avançado de automação assíncrona baseado em **Python** e **Playwright**, desenvolvido para estudo de automação web, testes de carga e simulação de visualizações com retenção orgânica de *watch time* no YouTube.

### Objetivos Centrais
- Simular navegação e comportamento de espectadores reais em vídeos individuais, playlists ou canais inteiros.
- **Modo Pesquisa Orgânica (*Search & Play*):** Buscar termos/títulos na home do YouTube e clicar nos resultados orgânicos para registrar fontes como *"Pesquisa do YouTube"* no YouTube Studio Analytics.
- Superar automaticamente interrupções do player do YouTube (pop-up "Continuar assistindo?", banners de consentimento de cookies e anúncios com botão "Pular anúncio").
- **Recuperação Adaptativa de Buffering:** Descongelar players estagnados em 3 níveis (Play/atalho 'k', clique forçado + frame skip, e reload preservando o watch time acumulado).
- Operar em múltiplos workers paralelos concorrentes com inicialização escalonada (*stagger ramp-up*).
- **Gerenciamento Inteligente de Proxies:** Pool de 100 proxies residenciais, quarentena automática de IPs bloqueados (30 min) e fallback infinito para rotação contínua.
- **Modo Ultra-Leve Global:** Bloqueio de imagens, fontes e anúncios, forçando 144p via localStorage e poupando até 50% de CPU/RAM.
- Oferecer controle dual: **Linha de Comando (CLI)** e **Dashboard Visual Web em tempo real** (FastAPI + WebSockets + Vanilla UI).
- Mitigar detecções automatizadas por meio de perfis de hardware randomizados (anti-fingerprint), micro-interações humanas e persistência de perfis/cookies.
- Persistir e auditar o histórico de rodadas e sessões em banco de dados local SQLite.

---

## 2. Arquitetura do Sistema e Estrutura de Código

```text
d:/Projetos/15 - Youtube View Bot/
├── config.yaml               # Arquivo padrão de configurações do bot
├── config.example.yaml       # Modelo de referência de configuração
├── env.example               # Modelo de variáveis de ambiente
├── proxies.txt               # Pool de 100 proxies residenciais pré-configurados
├── proxies.example.txt       # Modelo de lista de proxies
├── cookies.example.json      # Modelo de importação de cookies de sessão
├── urls.txt                  # Lista de vídeos alvo padrão (com suporte a "URL | palavra-chave")
├── iniciar_painel.bat        # Launcher de 1 clique para iniciar o painel web no Windows
├── requirements.txt          # Dependências do projeto (Playwright, FastAPI, Uvicorn, Typer, Rich, etc.)
├── tests/                    # Suíte de testes automatizados com pytest e pytest-asyncio (63 testes)
│   ├── test_config.py
│   ├── test_fingerprint.py
│   ├── test_helpers.py
│   ├── test_round_duration_and_loop.py
│   ├── test_browser_reuse.py
│   ├── test_youtube_parser.py
│   ├── test_history_db.py
│   ├── test_session_profiles.py
│   ├── test_performance_and_recovery.py
│   ├── test_search_and_play.py
│   └── test_web_api.py
└── src/
    ├── main.py               # Entrypoint principal (CLI + inicialização do servidor Web)
    ├── config.py             # Schema de configuração (Pydantic v2) e hierarquia de carregamento
    ├── orchestrator.py       # Gestão assíncrona de workers, loops de repetição e rotação de proxies
    ├── browser/
    │   ├── playwright_worker.py  # Processo Chromium persistente, reciclagem de BrowserContext, bloqueio de mídia
    │   └── fingerprint.py        # Injeção JS de perfis stealth (WebGL, Canvas 2D, Audio, Hardware)
    ├── youtube/
    │   ├── player.py             # Monitoramento de vídeo, auto-recovery de buffering, contagem e replay
    │   ├── search_flow.py        # Modo Search & Play (busca orgânica, cadência de digitação e clique)
    │   ├── ads.py                # Detecção e clique automático em 'Pular anúncio'
    │   ├── continue_watching.py  # Detecção e clique no diálogo 'Continuar assistindo'
    │   ├── interactions.py       # Micro-interações humanas (mouse jitter, hover, scroll sutil)
    │   └── parser.py             # Parser rápido de playlists e canais do YouTube (httpx + Playwright)
    ├── web/
    │   ├── app.py                # Rotas REST (/api/history, /api/start, etc.) e WebSockets
    │   ├── state.py              # StateManager singleton, buffer de sessões e auto-save SQLite
    │   └── static/
    │       ├── index.html        # Estrutura do dashboard visual com abas (Painel ao Vivo & Histórico)
    │       ├── styles.css        # Design system moderno escuro (Glassmorphism neon)
    │       └── app.js            # Lógica reativa, cliente WebSocket e módulo de histórico SQLite
    └── utils/
        ├── db.py                 # DatabaseManager: CRUD e persistência local SQLite (tabelas runs e run_sessions)
        ├── helpers.py            # Normalização de URLs, cookies, User-Agents e rotação de proxies
        └── logger.py             # Logging estruturado e rastreamento de métricas (JSONL)
```

---

## 3. Fluxo de Execução e Ciclo de Vida dos Workers

```mermaid
flowchart TD
    User([Usuário: CLI ou Web Hub]) --> Init[Carrega Configuração: config.py / BotConfig]
    Init --> Orch[BotOrchestrator: Inicia Tasks Assíncronas]
    Orch --> Monitor[Temporizador de Rodada: max_runtime_hours]
    
    subgraph PoolWorkers ["Pool de Workers Simultâneos"]
        W1[Worker 1: Stagger Delay 0s]
        W2[Worker 2: Stagger Delay 15s]
        WN[Worker N: Stagger Delay N*15s]
    end
    
    Orch --> PoolWorkers
    
    subgraph SessaoWorker ["Ciclo de Vida de Cada Worker"]
        BrowserInit[Playwright Chromium Reutilizado]
        NewContext[Criar BrowserContext Isolado + Anti-Fingerprint + Cookies]
        UltraLight[Filtro Ultra-Leve: Bloquear Imagens/Fontes + 144p LocalStorage]
        
        NavDecide{Modo Search & Play Ativado?}
        SearchFlow[Digitar Título na Busca + Rolar + Clicar no Vídeo]
        DirectNav[Navegação Direta: page.goto]
        
        CheckBlock{Bloqueio Google Sorry / CAPTCHA?}
        RotateIP[Cooldown 6-10s ou Auto-Substituição de IP após 3 Bloqueios]
        
        Cookies[Tratar Banners de Cookies]
        PlayLoop[Loop de Monitoramento do Player]
        
        StuckCheck{Player Travado / Buffering?}
        RecoveryNivel[Auto-Recovery: Nível 1 k/play -> Nível 2 clique/skip -> Nível 3 reload]
        
        MicroInteractions[Micro-Interações Humanas Aleatórias]
        HandleAds[Auto Skip Ads]
        HandleContinue[Auto Continue Watching]
        EndedCheck{Vídeo acabou antes da meta?}
        Replay[Reiniciar do Início]
        EndWatch{Watch Time Atingido?}
        NaturalPause[Pausa Natural entre Vídeos]
        NextCycle[Próximo Vídeo da Lista]
    end

    W1 --> BrowserInit
    BrowserInit --> NewContext --> UltraLight --> NavDecide
    NavDecide -- Sim --> SearchFlow --> CheckBlock
    NavDecide -- Não --> DirectNav --> CheckBlock
    
    CheckBlock -- Bloqueado --> RotateIP --> NextCycle
    CheckBlock -- Limpo --> Cookies --> PlayLoop
    
    PlayLoop --> StuckCheck
    StuckCheck -- Sim --> RecoveryNivel --> PlayLoop
    StuckCheck -- Não --> MicroInteractions --> HandleAds --> HandleContinue --> EndedCheck
    
    EndedCheck -- Sim --> Replay --> PlayLoop
    EndedCheck -- Não --> EndWatch
    EndWatch -- Não --> PlayLoop
    EndWatch -- Sim --> NaturalPause --> NextCycle --> NewContext

    Monitor -- Timeout Expirado --> StopAll[Finalização Graciosa: stop_event setado]
    StopAll --> CloseBrowsers[Fechamento de contextos e salvamento SQLite]
    CloseBrowsers --> Relatorio[Histórico Salvo em SQLite e Notificação Web]
```

---

## 4. Recursos Centrais Implementados

1. **Modo Pesquisa Orgânica (*Search & Play*):**
   - Em vez de tráfego direto, o worker digita o título ou palavra-chave na barra de busca do YouTube com digitação humanizada, rola os resultados e clica no vídeo correspondente.
   - Atribui visualizações no YouTube Studio como **"Pesquisa do YouTube" (YouTube Search)**.
   - Resolução de títulos por endpoint oEmbed público do YouTube e suporte a palavras-chave customizadas (`URL | termo`). Fallback transparente para navegação direta caso não rankeie.
2. **Modo Ultra-Leve Global (`block_heavy_media`):**
   - Interceptação de rotas via `context.route` abortando imagens, fontes externas, avatares (`yt3.ggpht.com`), thumbnails (`i.ytimg.com`) e telemetria de anúncios (`doubleclick.net`, `googleads`).
   - Força resolução 144p (`tiny`) no `localStorage` do YouTube antes de carregar o player.
   - Economia de até 50% de CPU/RAM e até 90% de dados de rede.
3. **Auto-Recuperação de Player Travado / Buffering (`auto_player_recovery`):**
   - Recuperação escalonada em 3 níveis (Nível 1: Play/'k', Nível 2: clique forçado + frame skip, Nível 3: recarregamento da página preservando o watch time acumulado).
   - Feedback visual dinâmico no card do worker: `"Recuperando (Nx)"`.
4. **Gerenciamento Inteligente de Proxies:**
   - Suporte a proxies residenciais e rotativos com pool de 100 IPs (`proxies.txt`).
   - Quarentena inteligente de 30 minutos para IPs que sofreram 3 bloqueios.
   - Fallback dinâmico infinito para gateways que aceitam IDs de sessão únicos (`sessid.w{worker_id}_{uuid}`).
5. **Reuso Eficiente de Processos Chromium:**
   - Processo `.exe` do Chromium mantido ativo continuamente por worker, reciclando apenas `BrowserContext` leve e isolado a cada sessão.
6. **Parser Automático de Playlists e Canais:**
   - Extrai automaticamente todos os vídeos de links de playlists (`playlist?list=...`) ou canais (`/@canal/videos`), com botão dedicado no Dashboard Web ("✨ Extrair Playlist/Canal").
7. **Histórico e Persistência de Execuções (SQLite):**
   - Registro automático de cada rodada (`runs`) e sessão de vídeo (`run_sessions`) em banco local SQLite (`bot_history.db`).
   - Aba visual de Histórico no painel com KPIs consolidados e modal de auditoria por sessão.
8. **Perfis Persistentes & Cookies de Sessão:**
   - Suporte a cookies JSON (Playwright/Cookie-Editor) e Netscape (tab-separated), com opção de perfil persistente por worker (`profiles/worker_{id}`).
9. **Escalonamento Gradual (*Worker Stagger Delay*):**
   - Inicialização espaçada entre workers (padrão 15s) para evitar disparos de requisições simultâneas em massa no mesmo IP/rede.
10. **Anti-Fingerprint Determinístico:**
    - Assinaturas WebGL de GPUs reais, micro-ruído imperceptível no Canvas 2D e AudioContext, além de contagens customizadas de CPU e memória RAM por worker.
11. **Simulação de Micro-Comportamento Humano:**
    - Movimento de cursor suave (*mouse jitter*), hover temporário no player e rolagem de página (*natural scroll*).
12. **Superação de Interrupções do Player:**
    - Detecção contínua e clique no diálogo "Continuar assistindo?", bypass de cookies de consentimento e pulo automático de anúncios (*Skip Ad*).
13. **Loop Contínuo e Duração da Rodada:**
    - Temporizador global configurado em horas com encerramento gracioso e rotação cíclica de vídeos.
14. **Dashboard Web em Tempo Real (FastAPI + WebSockets):**
    - Métricas ao vivo, cards de workers reativos, streaming de logs e controle total de inicialização/parada.

---

## 5. Matriz de Gargalos Originais vs. Soluções Implementadas

| Área | Limitação Original (v1.x) | Solução Implementada (v2.4) | Status |
|---|---|---|---|
| **Rede / IP** | Ausência de suporte a Proxy (todos no IP local). | Suporte completo a Proxies HTTP/SOCKS5, pool de 100 IPs, quarentena de 30 min e fallback infinito sob demanda. | ✅ **Resolvido** |
| **Consumo de Hardware** | `chromium.launch()` aberto e fechado a cada vídeo. | Reuso contínuo do processo Chromium por worker + Modo Ultra-Leve Global bloqueando imagens/fontes e forçando 144p. | ✅ **Resolvido** |
| **Persistência de Dados** | Estado puramente em memória e logs voláteis. | Persistência relacional em SQLite leve com aba dedicada de Histórico e modal de auditoria no Web Hub. | ✅ **Resolvido** |
| **Entrada de Vídeos** | Apenas links de vídeos individuais eram aceitos. | Parser híbrido (httpx + Playwright) com expansão automática de Playlists e Canais na CLI e na Web. | ✅ **Resolvido** |
| **Resolução de Bloqueio** | Worker bloqueado era encerrado sem recuperação. | Detecção ativa do Google Sorry, cooldown de esfriamento e auto-substituição de IP após 3 bloqueios. | ✅ **Resolvido** |
| **Identidade & Retenção** | Apenas visitante anônimo deslogado. | Suporte a perfis de usuário persistentes e injeção universal de cookies (JSON e Netscape). | ✅ **Resolvido** |
| **Fonte de Tráfego** | Acesso direto (`Direct/Unknown`), penalizado pelo YouTube. | **Modo Search & Play:** digitação humana na busca do YouTube e clique orgânico no resultado ("YouTube Search"). | ✅ **Resolvido** |
| **Buffering / Freeze** | Travamentos de conexão paralisavam o player. | **Auto-Player Recovery:** mecanismo adaptativo de 3 níveis que recupera a reprodução preservando o watch time. | ✅ **Resolvido** |

---

## 6. Próximos Passos & Oportunidades Futuras (Backlog)

Todas as prioridades essenciais de rede, performance, automação, persistência e tráfego orgânico foram **100% concluídas**. Para versões subsequentes (v2.5+), as seguintes melhorias estratégicas podem ser consideradas:

### Prioridade 4: Relatórios & Automação de Agendamento
- [ ] **Exportação de Relatórios de Histórico (CSV / JSON) no Dashboard Web:**
  - Botão interativo na aba "Histórico de Rodadas" para download direto de planilhas consolidadas contendo métricas de cada sessão de vídeo realizada.
- [ ] **Agendador de Sessões / Modo Janela de Audiência (Scheduler):**
  - Configuração de horários de atividade programados (ex: picos de audiência diurnos vs. repouso durante a madrugada) para simulação de curvas orgânicas de público.
- [ ] **Integração com Solvers Externos de CAPTCHA (2Captcha / CapSolver):**
  - Módulo opcional para resolução automática de reCAPTCHA em casos de redes sem acesso a proxies residenciais limpos.
