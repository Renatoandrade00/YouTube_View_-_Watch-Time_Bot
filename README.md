# YouTube View & Watch-Time Bot

Automação assíncrona em Python com **Playwright** para simulação realista de visualizações, retenção de *watch time*, isolamento avançado de rede via proxies e superação automática do diálogo de inatividade ("Continuar assistindo") no YouTube.

---

## ⚠️ AVISO LEGAL E DE RESPONSABILIDADE (DISCLAIMER)

> **Atenção:** O uso de ferramentas automatizadas para inflar artificialmente visualizações, watch time ou qualquer métrica de engajamento viola os [Termos de Serviço do YouTube](https://www.youtube.com/static?template=terms) e as diretrizes da comunidade sobre Fake Engagement.
> 
> O descumprimento pode acarretar em:
> - Invalidação e remoção de visualizações
> - Aplicação de avisos/strikes no canal
> - Remoção de vídeos ou suspensão de monetização
> - Encerramento/banimento definitivo da conta Google/YouTube
> 
> **Este projeto foi desenvolvido estritamente para fins educacionais, de pesquisa em automação de navegadores e testes de carga em ambientes controlados.** O usuário final assume total responsabilidade pelo seu uso e pelas consequências decorrentes.

---

- **Parser Automático de Playlists e Canais:**
  - Suporte nativo para links de playlists (`https://www.youtube.com/playlist?list=...`) e abas de vídeos de canais (`https://www.youtube.com/@Canal/videos` ou `/@Canal`).
  - Extração híbrida em duas camadas (HTTP direto via `httpx` com fallback inteligente em Playwright).
  - Botão interativo no Dashboard Web ("✨ Extrair Playlist/Canal") que preenche a lista na hora, além de resolução automática na CLI e em arquivos `urls.txt`.
- **Gerenciamento Inteligente de Proxies (Pool + Quarentena + Fallback Infinito):**
  - Suporte a proxies residenciais e rotativos (HTTP/SOCKS5 com autenticação).
  - **Quarentena Inteligente:** IPs que sofrem bloqueio entram automaticamente em quarentena de 30 minutos para resfriamento de rede.
  - **Auto-Substituição após 3 Bloqueios:** Detecta sinalizações do Google e rotaciona o IP sem interromper a execução do worker.
  - **Fallback Dinâmico Infinito:** Gera sessões únicas sob demanda (`sessid.w{worker_id}_{uuid}`) para provedores como DataImpulse, Smartproxy e BrightData, garantindo fornecimento contínuo de IPs sem risco de esgotamento.
  - **Modo Economia de Banda:** Força qualidade 144p (`tiny`) e bloqueia requisições de anúncios, rastreadores e imagens secundárias, reduzindo o consumo de dados em até 90%.
- **Modo Ultra-Leve Global (`block_heavy_media`):**
  - Interceptação ativa de requisições de avatares (`yt3.ggpht.com`), thumbnails (`i.ytimg.com`), fontes externas, anúncios e imagens decorativas em qualquer execução (local ou com proxy).
  - Pré-configura localStorage do YouTube para forçar 144p (`tiny`), reduzindo em até 50% o consumo de CPU e memória RAM das instâncias de Chromium.
- **Recuperação Adaptativa de Buffering & Player Travado (`auto_player_recovery`):**
  - Monitoramento adaptativo de estagnação de `currentTime` e `readyState` do player HTML5.
  - Recuperação em 3 níveis escalonados:
    - **Nível 1 (~10s parado):** Disparo de evento Play e atalho 'k'.
    - **Nível 2 (~20s parado):** Clique forçado no contêiner do player e avanço de frame (+1s).
- **Modo Pesquisa Orgânica ("Search & Play"):**
  - Em vez de acessar a URL direta (fonte "Direct/Unknown" no Analytics), o worker entra na home do YouTube, digita o título do vídeo ou palavra-chave customizada com cadência de digitação humana e rola os resultados até localizar e clicar no vídeo orgânico.
  - Registra a fonte de tráfego como **"Pesquisa do YouTube" (YouTube Search)** no YouTube Studio, conferindo máxima autoridade, SEO e retenção indetectável.
  - Suporte a palavras-chave automáticas (via oEmbed público leve do YouTube) ou personalizadas (`URL | palavra-chave` ou `palavra;URL`).
  - Fallback transparente e automático para navegação direta caso o vídeo não seja localizado após 4 rolagens.
- **Anti-Fingerprint Determinístico e Avançado:**
  - Assinaturas WebGL de GPUs reais (NVIDIA RTX, Intel Iris Xe, AMD RX).
  - Micro-ruído imperceptível no Canvas 2D e AudioContext.
  - Variação dinâmica de núcleos de CPU e memória RAM por worker.
- **Simulação de Micro-Comportamento Humano:**
  - Movimentação suave de cursor (mouse jitter com interpolação polinomial).
  - Hover temporário interativo sobre elementos do player.
  - Rolagem suave de página (scroll natural) e pausas randômicas.
- **Escalonamento Gradual de Workers (*Stagger Ramp-up*):**
  - Inicialização espaçada entre instâncias para evitar disparos simultâneos de requisições de rede no mesmo segundo.
- **Modo Contínuo & Rotação de Vídeos:**
  - Temporizador global de rodada (`max_runtime_hours` / `--duration-hours`).
  - Alternância cíclica entre vídeos da lista ou repetição contínua após o término da reprodução.
- **Superação de Interrupções do Player:**
  - Detecção contínua e clique no diálogo "Continuar assistindo?".
  - Bypass de banners de consentimento de cookies da Google/YouTube.
  - Pulo automático de anúncios ("Skip Ad").
- **Perfis Persistentes & Injeção de Cookies de Sessão:**
  - Suporte a perfis de usuário persistentes por worker (`profiles/worker_{id}/storage_state.json`), preservando login no Google/YouTube, cookies, histórico e preferências de reprodução.
  - Injeção flexível de arquivos de cookies (`--cookies-file` / `cookies.json`) nos formatos padrão JSON (Playwright/Cookie-Editor) e Netscape (tab-separated), com suporte a cookies específicos por worker (`worker_{id}.json`).
  - Reduz drasticamente o descarte de visualizações pelo algoritmo do YouTube ao simular tráfego de usuários com histórico orgânico.
- **Histórico e Persistência de Rodadas (SQLite):**
  - Armazenamento automático e local de cada rodada finalizada (`runs`) e de suas sessões de vídeo individuais (`run_sessions`) em banco SQLite leve (zero dependências externas).
  - Aba dedicada no Dashboard Web ("📜 Histórico de Rodadas") com KPIs consolidados (total de rodadas, horas acumuladas, taxa de sucesso, popups superados).
  - Modal interativo com detalhamento de cada sessão executada (watch time real vs alvo, URLs, status e mensagens de erro).
  - Endpoints REST para consulta paginada, detalhamento, exclusão individual e limpeza de histórico (`/api/history`).
- **Arquitetura 100% Assíncrona:**
  - Controle rigoroso de concorrência com `asyncio.Semaphore`.
  - Encerramento limpo e gracioso (`Graceful Shutdown`) ao pressionar `Ctrl+C` ou clicar em "Parar".

---

## 🛠️ Requisitos e Instalação

1. **Python 3.10+** instalado.
2. Clone o repositório:
   ```bash
   git clone https://github.com/Renatoandrade00/YouTube_View_-_Watch-Time_Bot.git
   cd YouTube_View_-_Watch-Time_Bot
   ```
3. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
5. Instale o navegador Chromium do Playwright:
   ```bash
   playwright install chromium
   ```

---

## ⚙️ Configuração do Ambiente

O projeto suporta configuração via **arquivo YAML**, **variáveis de ambiente (`.env`)** ou **parâmetros CLI**.

### 1. Arquivo de Configuração (`config.yaml`)
Copie o modelo de exemplo para criar sua configuração local:
```bash
cp config.example.yaml config.yaml
```
Edite os parâmetros de execução, watch time (em segundos na CLI/YAML), URLs e configurações de proxy.

### 2. Variáveis de Ambiente (`.env`)
Copie o arquivo de exemplo:
```bash
cp env.example .env
```

### 3. Configuração de Proxies (`proxies.txt`)
Para utilizar proxies residenciais dedicados ou rotativos:
1. Copie o arquivo modelo:
   ```bash
   cp proxies.example.txt proxies.txt
   ```
2. Insira seus proxies (um por linha):
   ```text
   http://usuario:senha@gateway.provedor.com:porta
   ```
> **Nota de Segurança:** Os arquivos `config.yaml`, `.env` e `proxies.txt` estão incluídos no `.gitignore` para prevenir o vazamento de credenciais.

---

## 🌐 Modo Visual Web (Dashboard no Navegador)

O sistema conta com um **Dashboard Web integrado** de alta produtividade:

### Como iniciar o painel web:
- **No Windows (1 Clique):** Dê um duplo clique no arquivo [`iniciar_painel.bat`](iniciar_painel.bat).
- **Via Terminal:**
   ```bash
   python -m src.main --web --port 8000
   ```

O painel será aberto automaticamente no navegador em `http://localhost:8000`.

### Destaques do Painel:
* **Abas Interativas:** Alterne instantaneamente entre o **Painel ao Vivo** e o **Histórico de Rodadas**.
* **Entrada Rápida:** Cole URLs diretamente, importe do arquivo `urls.txt` ou extraia playlists/canais com 1 clique.
* **Configuração em Minutos:** Ajuste de tempo de exibição mínimo e máximo diretamente em minutos.
* **Seção de Proxy:** Ative o uso de proxies, defina o arquivo da lista e acompanhe o IP mascarado atribuído a cada worker.
* **Cards de Workers:** Exibição em tempo real do status, vídeo atual, IP ativo e barra de progresso.
* **Console de Logs:** Streaming de mensagens via WebSocket em tempo real.
* **Histórico com SQLite:** Registro persistente de rodadas anteriores, KPIs consolidados e modal de inspeção de cada sessão de vídeo.

---

## 💻 Uso via CLI (Linha de Comando)

### 1. Execução rápida com vídeo único
```bash
python -m src.main --url "https://www.youtube.com/watch?v=SEU_VIDEO_ID" --workers 2 --min-watch 45 --max-watch 120
```

### 2. Execução com lista de vídeos e duração da rodada
```bash
python -m src.main --urls-file urls.txt --workers 4 --duration-hours 2.5
```

### 3. Execução utilizando lista de proxies
```bash
python -m src.main --urls-file urls.txt --workers 4 --proxy --proxies-file proxies.txt
```

### 4. Modo Headless Ultra-Leve (Economia de CPU/RAM com Auto-Recuperação)
```bash
python -m src.main --urls-file urls.txt --workers 5 --headless --block-heavy-media --auto-recovery
```

### 5. Modo Pesquisa Orgânica ("Search & Play")
```bash
python -m src.main --urls-file urls.txt --workers 3 --search-and-play
```

---

## 📁 Estrutura do Projeto

```text
├── config.example.yaml        # Modelo de configuração do bot
├── env.example                # Modelo de variáveis de ambiente
├── proxies.example.txt        # Modelo de lista de proxies
├── cookies.example.json       # Modelo de importação de cookies de sessão
├── urls.txt                   # Lista padrão de URLs alvo
├── iniciar_painel.bat         # Launcher rápido do painel web para Windows
├── requirements.txt           # Dependências do projeto
├── tests/                     # Suíte de testes unitários e de integração (51 testes)
└── src/
    ├── main.py                # Ponto de entrada CLI e inicialização do servidor Web
    ├── config.py              # Validação e hierarquia de configurações (Pydantic)
    ├── orchestrator.py        # Orquestrador assíncrono, pool de workers e rotação de proxies
    ├── browser/
    │   ├── playwright_worker.py  # Gerenciamento de instâncias, storage_state e cookies
    │   └── fingerprint.py        # Injeção de perfis anti-fingerprint (WebGL, Canvas, Audio)
    ├── youtube/
    │   ├── player.py             # Reprodução, monitoramento, detecção de CAPTCHA e 144p
    │   ├── ads.py                # Detecção e clique em 'Pular anúncio'
    │   ├── continue_watching.py  # Detecção e clique em 'Continuar assistindo'
    │   ├── interactions.py       # Micro-interações humanas (mouse jitter, hover, scroll)
    │   └── parser.py             # Extração rápida de playlists e canais do YouTube
    ├── web/
    │   ├── app.py                # Rotas REST e endpoints WebSocket (FastAPI)
    │   ├── state.py              # StateManager singleton e broadcast em tempo real
    │   └── static/               # Frontend SPA (Vanilla JS + Glassmorphism UI)
    └── utils/
        ├── db.py                 # Persistência e consultas em SQLite (runs e run_sessions)
        ├── helpers.py            # Rotação de sessão, mascaramento e parser de cookies (JSON/Netscape)
        └── logger.py             # Logging estruturado e gravação de métricas JSONL
```

---

## 🧪 Testes Automatizados

O projeto conta com uma suíte de testes automatizados com cobertura completa para validação de regras de configuração, injeção de fingerprints, rotação de proxies, quarentena, persistência de Chromium, parser de playlists/canais, histórico SQLite e perfis/cookies persistentes (**51 testes automatizados**):

```bash
pytest
```

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte o arquivo de licença para mais informações.
