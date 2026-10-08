# YouTube View & Watch-Time Bot

Automação em Python com **Playwright** para simulação de visualizações, retenção de watch time e superação automática do diálogo de inatividade ("Continuar assistindo") no YouTube.

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

## 🚀 Funcionalidades (MVP)

- **Perfis Anti-Fingerprint Únicos:** Randomização de assinaturas WebGL (vendor/renderer de GPUs reais), micro-ruído imperceptível no Canvas 2D e AudioContext, além de variação de núcleos de CPU e memória RAM por worker.
- **Simulação de Micro-Comportamento Humano:** Movimentação natural de cursor (mouse jitter gradual), hover temporário no player de vídeo e rolagem suave de página (scroll sutil).
- **Modo Contínuo & Rotação Inteligente:** Execução contínua por horas (`--duration-hours`) alternando automaticamente para o próximo vídeo da lista com pausas naturais configuráveis.
- **Suporte a Vídeo Único ou Lista:** Aceita URL individual via CLI ou arquivo com múltiplas URLs.
- **Watch Time Dinâmico:** Intervalos configuráveis (`min_watch` e `max_watch`) com randomização por sessão.
- **Superação de "Continuar Assistindo":** Monitoramento ativo e clique automático no diálogo de pausa por inatividade do player.
- **Tratamento de Anúncios:** Detecção contínua e clique em botões de "Pular anúncio" / "Skip Ad".
- **Aceitação de Cookies:** Bypass automático de modais de consentimento do Google/YouTube.
- **Múltiplos Workers Locais:** Execução paralela assíncrona com controle de concorrência (`asyncio.Semaphore`).
- **Navegação Isolada:** Cada worker opera em um contexto de navegador independente (cookies limpos, cache separado).
- **Encerramento Seguro:** Captura de `Ctrl+C` (`SIGINT`) com fechamento garantido de todas as instâncias do navegador.

---

## 🛠️ Requisitos e Instalação

1. **Python 3.10+** instalado.
2. Clone o repositório ou navegue até o diretório do projeto:
   ```bash
   cd "d:/Renato/PROJETOS/13 - BOT YOUTUBE"
   ```
3. Crie e ative um ambiente virtual (recomendado):
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
5. Instale os navegadores do Playwright (Chromium):
   ```bash
   playwright install chromium
   ```

---

## 💻 Uso Rápido via CLI

### 1. Visualização de vídeo único com 2 workers
```bash
python -m src.main --url "https://www.youtube.com/watch?v=SEU_VIDEO_ID" --workers 2 --min-watch 45 --max-watch 90
```

### 2. Modo Headless (segundo plano)
```bash
python -m src.main --url "https://www.youtube.com/watch?v=SEU_VIDEO_ID" --headless
```

### 3. Usando lista de vídeos
Crie um arquivo `urls.txt` com uma URL por linha:
```bash
python -m src.main --urls-file urls.txt --workers 3 --total-views 15
```

---

## 📁 Estrutura do Código

```text
src/
├── main.py                  # CLI principal e tratamento de encerramento
├── config.py                # Leitura de variáveis de ambiente, YAML e flags CLI
├── orchestrator.py          # Pool assíncrono de workers e métricas de execução
├── browser/
│   └── playwright_worker.py # Inicialização, isolamento de contextos e fechamento
├── youtube/
│   ├── player.py            # Navegação, cookies, play e monitor de reprodução
│   ├── continue_watching.py # Polling e clique no popup 'Continuar assistindo'
│   └── ads.py               # Detecção e clique em 'Pular anúncio'
└── utils/
    ├── logger.py            # Logs estruturados e resumo de sessões
    └── helpers.py           # Delays randômicos e rotação de User-Agent
```
