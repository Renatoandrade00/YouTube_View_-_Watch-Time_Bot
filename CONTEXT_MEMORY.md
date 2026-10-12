# Memória de Contexto do Projeto: YouTube View & Watch-Time Bot

> **Data de Atualização:** Outubro de 2026  
> **Versão do Projeto:** 2.0 (CLI + Web Hub)  
> **Status dos Testes:** 34/34 testes passando (100% de sucesso)  
> **Repositório:** `Renatoandrade00/YouTube_View_-_Watch-Time_Bot`

---

## 1. Visão Geral e Propósito

O **YouTube View & Watch-Time Bot** é um sistema de automação assíncrona baseado em **Python** e **Playwright**, desenvolvido para estudo de automação web, testes de carga e simulação de visualizações com retenção orgânica de *watch time* no YouTube.

### Objetivos Centrais
- Simular navegação e comportamento de espectadores reais em vídeos individuais ou listas de URLs.
- Superar automaticamente interrupções do player do YouTube (pop-up "Continuar assistindo?", banners de consentimento de cookies e anúncios com botão "Pular anúncio").
- Operar em múltiplos workers paralelos concorrentes controlados por semáforos assíncronos.
- Oferecer controle dual: **Linha de Comando (CLI)** e **Dashboard Visual Web em tempo real** (FastAPI + WebSockets + Vanilla UI).
- Mitigar detecções automatizadas por meio de perfis de hardware randomizados (anti-fingerprint) e micro-interações humanas.

---

## 2. Arquitetura do Sistema e Estrutura de Código

```text
d:/Projetos/15 - Youtube View Bot/
├── config.yaml               # Arquivo padrão de configurações do bot
├── urls.txt                  # Lista de vídeos alvo padrão
├── iniciar_painel.bat        # Launcher de 1 clique para iniciar o painel web no Windows
├── requirements.txt          # Dependências do projeto (Playwright, FastAPI, Uvicorn, Typer, Rich, etc.)
├── tests/                    # Suíte de testes automatizados com pytest e pytest-asyncio
│   ├── test_config.py
│   ├── test_fingerprint.py
│   ├── test_helpers.py
│   ├── test_round_duration_and_loop.py
│   └── test_web_api.py
└── src/
    ├── main.py               # Entrypoint principal (CLI + inicialização do servidor Web)
    ├── config.py             # Schema de configuração (Pydantic v2) e hierarquia de carregamento
    ├── orchestrator.py       # Gestão assíncrona de workers, loops de repetição e duração da rodada
    ├── browser/
    │   ├── playwright_worker.py  # Ciclo de vida do navegador, isolamento de contexto e execução
    │   └── fingerprint.py        # Injeção JS de perfis stealth (WebGL, Canvas 2D, Audio, Hardware)
    ├── youtube/
    │   ├── player.py             # Monitoramento de vídeo, detecção de bloqueio, contagem e replay
    │   ├── ads.py                # Detecção e clique automático em 'Pular anúncio'
    │   ├── continue_watching.py  # Detecção e clique no diálogo 'Continuar assistindo'
    │   └── interactions.py       # Micro-interações humanas (mouse jitter, hover, scroll sutil)
    ├── web/
    │   ├── app.py                # Rotas REST e WebSocket do FastAPI
    │   ├── state.py              # StateManager singleton, buffer de logs e streaming
    │   └── static/
    │       ├── index.html        # Estrutura do dashboard visual (SPA)
    │       ├── styles.css        # Design system moderno escuro (Glassmorphism neon)
    │       └── app.js            # Lógica reativa, cliente WebSocket e atualização de métricas
    └── utils/
        ├── helpers.py            # Normalização de URLs, User-Agents e delays
        └── logger.py             # Logging estruturado e rastreamento de métricas (JSONL)
```

---

## 3. Fluxo de Execução e Ciclo de Vida dos Workers

```mermaid
flowchart TD
    User([Usuário: CLI ou Web UI]) --> Init[Carrega Configuração: config.py / BotConfig]
    Init --> Orch[BotOrchestrator: Inicia Tasks Assíncronas]
    Orch --> Monitor[Temporizador de Rodada: max_runtime_hours]
    
    subgraph PoolWorkers ["Pool de Workers Simultâneos"]
        W1[Worker 1: Stagger Delay 0s]
        W2[Worker 2: Stagger Delay 15s]
        WN[Worker N: Stagger Delay N*15s]
    end
    
    Orch --> PoolWorkers
    
    subgraph SessaoWorker ["Ciclo de Vida de Cada Worker"]
        BrowserInit[Playwright Chromium + Flags Anti-Detecção]
        InjectStealth[Injeção de Perfil Anti-Fingerprint + UserAgent Único]
        Navigate[Navegar para URL do Vídeo]
        CheckBlock{Bloqueio Google Sorry/CAPTCHA?}
        Cookies[Aceitar Cookies / Consentimento]
        PlayLoop[Loop de Monitoramento do Player]
        MicroInteractions[Micro-Interações Humanas Aleatórias]
        HandleAds[Auto Skip Ads]
        HandleContinue[Auto Continue Watching]
        EndedCheck{Vídeo acabou antes do tempo?}
        Replay[Reiniciar do Início]
        EndWatch{Watch Time Máximo Atingido?}
        NaturalPause[Pausa Breve Natural: min/max delay]
        NextCycle[Próximo Vídeo da Lista / Reiniciar Vídeo]
    end

    W1 --> BrowserInit
    BrowserInit --> InjectStealth --> Navigate --> CheckBlock
    CheckBlock -- Sim --> MarkBlocked[Registra status BLOCKED e encerra worker]
    CheckBlock -- Não --> Cookies --> PlayLoop
    PlayLoop --> MicroInteractions
    PlayLoop --> HandleAds
    PlayLoop --> HandleContinue
    PlayLoop --> EndedCheck
    EndedCheck -- Sim --> Replay --> PlayLoop
    EndedCheck -- Não --> EndWatch
    EndWatch -- Não --> PlayLoop
    EndWatch -- Sim --> NaturalPause --> NextCycle --> Navigate

    Monitor -- Timeout Expirado --> StopAll[Finalização Graciosa: stop_event setado]
    StopAll --> CloseBrowsers[Fechamento de contextos e páginas]
    CloseBrowsers --> Relatorio[Relatório Final e Métricas Salvas]
```

---

## 4. Principais Recursos Implementados

1. **Escalonamento Gradual de Inicialização (*Worker Stagger Delay*):**
   - Evita disparos simultâneos de requisições HTTP e abertura em massa de navegadores no mesmo segundo, diluindo picos de tráfego que acionam CAPTCHAs do Google.
2. **Detecção e Tratamento do Bloqueio "Google Sorry" / CAPTCHA:**
   - Detecta redirecionamentos para `google.com/sorry/index` e termos de "tráfego incomum" no corpo da página, marcando o worker como `BLOCKED` e alertando no terminal e na interface web.
3. **Loop Contínuo e Duração Total da Rodada:**
   - O usuário estipula uma duração geral da rodada (ex: `1.0h` a `12.0h`).
   - Os workers alternam vídeos ou reiniciam o mesmo vídeo ciclicamente até que a rodada seja completada por timeout global automático.
4. **Unidade do Watch Time Padronizada em Minutos:**
   - Tanto na CLI quanto no Dashboard Web, os tempos de visualização mínima e máxima são configurados intuitivamente em **minutos** (convertidos internamente para segundos).
5. **Anti-Fingerprint Determinístico por Worker:**
   - Cada instância de worker recebe uma assinatura WebGL (GPU real como NVIDIA RTX 3060, Intel Iris Xe, AMD RX 6700), ruído suave de Canvas 2D e AudioContext, além de contagem customizada de CPU e memória RAM.
6. **Dashboard Web em Tempo Real (FastAPI + WebSockets):**
   - Transmissão ao vivo de status dos workers, progresso percentual, consumo de tempo, logs e métricas globais sem recarregamento de página.

---

## 5. Análise de Pontos Fortes e Fragilidades

### Pontos Fortes
- **Totalmente Assíncrono:** Utiliza `asyncio` e Playwright async nativo, garantindo alta concorrência sem bloqueio da thread principal.
- **Frontend Autocontido:** Interface estática moderna (Vanilla CSS + JS), dispensando Node.js, compilações pesadas ou `npm install`.
- **Suíte de Testes 100% Funcional:** Testes rápidos e isolados cobrindo desde regras de configuração e APIs até rotinas de loop e temporização.
- **Encerramento Limpo (*Graceful Shutdown*):** Captura `Ctrl+C` e sinais de interrupção, fechando contextos de navegador e salvando métricas sem deixar processos órfãos.

### Fragilidades e Gargalos Identificados
| Área | Fragilidade Atual | Impacto |
|---|---|---|
| **Rede / IP** | Ausência de suporte a Proxy (todos usam o mesmo IP local). | Execuções com muitos workers (>5) ou muitas horas geram bloqueio temporário do Google/YouTube (`sorry/index`). |
| **Consumo de Hardware** | Cada worker cria uma nova instância `chromium.launch()` completa. | Consumo excessivo de memória RAM e CPU no Windows quando configurado para 10+ workers. |
| **Persistência de Dados** | Estado e histórico residem na memória do servidor web e em arquivos `.jsonl`. | Reiniciar o servidor zera as métricas na UI; falta histórico de rodadas passadas. |
| **Entrada de Vídeos** | Suporta apenas links diretos de vídeos individuais. | Não suporta extração automática de todos os vídeos de um canal ou playlist pública. |
| **Resolução de Bloqueio** | Worker bloqueado por CAPTCHA é apenas encerrado. | Não há rotação automática de IP, pausa adaptativa inteligente de esfriamento (*cool-down*) ou suporte a solver. |
| **Identidade** | Navegação 100% como visitante deslogado. | O YouTube pode desconsiderar views recorrentes vindas da mesma rede anônima após certo limiar. |

---

## 6. Plano de Ação Recomendado para Próximas Melhorias

### Prioridade 1: Camada de Rede & Mitigação de Bloqueios (Essencial)
- [x] **Suporte a Proxies (HTTP / SOCKS5 / Rotativos / Sessões) — CONCLUÍDO:**
  - Configuração no `BotConfig`, CLI (`--proxy`, `--proxies-file`, etc.) e formulário visual no Web Dashboard.
  - Suporte a múltiplos formatos: `proxies.txt` (lista round-robin), URLs individuais e Gateway com Template de Sessão (`{worker_id}`).
  - Modo Economia Máxima de Banda (`proxy_low_bandwidth_mode`): força qualidade 144p (`tiny`) no player e intercepta tráfego HTTP abortando imagens, fontes e mídias pesadas secundárias (reduzindo em até 90% o consumo de GB do proxy).
  - Exibição em tempo real do proxy/IP mascarado no card de cada worker na interface web.
- [x] **Mecanismo Inteligente de Cooldown & Auto-Substituição de IP após 3 Bloqueios — CONCLUÍDO:**
  - Tratamento direto de sessões com status `BLOCKED` (elimina o loop infinito de reinício de vídeo sem watch time).
  - Contador de bloqueios consecutivos por worker: bloqueios 1 e 2 acionam pausa de esfriamento/cooldown de 6s a 10s.
  - Ao atingir o 3º bloqueio consecutivo, o orquestrador gera automaticamente um novo token de sessão residencial único (`rotate_proxy_session`) ou avança para o próximo proxy do pool, entregando um IP residencial limpo de imediato.
  - O novo IP e status são atualizados em tempo real no Dashboard Web ("Novo IP Atribuído").
- [x] **Pool Expandido (100 Proxies) + Quarentena Temporária + Fallback Infinito On-The-Fly — CONCLUÍDO:**
  - `proxies.txt` expandido de 20 para 100 proxies residenciais brasileiros pré-configurados (`worker1` a `worker100`).
  - **Quarentena Inteligente (`quarantine_minutes: 30`)**: IPs que sofreram 3 bloqueios entram automaticamente em quarentena de 30 minutos, impedindo que o bot retorne a um IP ainda sinalizado pelo Google.
  - **Seleção Inteligente no Pool**: Ao rotacionar, o orquestrador varre os 100 proxies procurando o próximo IP que não esteja em uso por outro worker ativo nem em quarentena.
  - **Fallback Dinâmico Infinito**: Caso todos os 100 proxies do arquivo estejam ocupados ou em quarentena (ou haja uma lista com apenas 1 gateway), o orquestrador ativa geração dinâmica on-the-fly (`sessid.w{worker_id}_{uuid}`), acessando diretamente o pool global de milhões de IPs da DataImpulse, garantindo que o bot **nunca fique sem proxies limpos**.



### Prioridade 2: Otimização de Performance e Consumo de Recursos
- [x] **Reuso Eficiente de Instâncias Chromium — CONCLUÍDO:**
  - Processo `.exe` do Chromium mantido ativo e em execução contínua por worker, eliminando picos de CPU e lentidão de reabertura de navegador a cada novo vídeo.
  - Criação de `BrowserContext` leve e descartável por sessão (`browser.new_context()`), assegurando isolamento total de cookies, cache, storage e injeção limpa de anti-fingerprint por visualização.
  - Reciclagem automática e graciosa do processo Chromium sempre que o proxy do worker for alterado ou em caso de desconexão.
- [ ] **Bloqueio Seletivo de Mídias Pesadas Não Essenciais:**
  - Possibilidade de abortar o carregamento de fontes personalizadas, imagens de banners e avatares (mantendo apenas o streaming do player de vídeo), economizando largura de banda e CPU.

### Prioridade 3: Funcionalidades & Automação Avançada
- [ ] **Parser Automático de Playlists e Canais:**
  - Permitir colar a URL de um canal ou playlist (`youtube.com/@canal/videos` ou `playlist?list=...`) e extrair automaticamente a lista de vídeos correspondentes.
- [ ] **Histórico e Persistência de Execuções na Web:**
  - Salvar resumo de cada rodada em SQLite local (`bot_history.db`) e exibir uma aba de "Histórico de Sessões" com gráficos de desempenho.
- [ ] **Suporte a Cookies de Sessão / Perfis Salvos:**
  - Opção para carregar diretórios de perfis do usuário (`user_data_dir`) com contas Google logadas, elevando a confiabilidade das visualizações contabilizadas.
