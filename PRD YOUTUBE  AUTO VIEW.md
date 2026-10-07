# PRD — YouTube View & Watch-Time Bot

**Versão:** 1.0  
**Data:** 07 de outubro de 2026  
**Status:** Rascunho para desenvolvimento  
**Stack principal:** Python + Playwright (preferencial) ou Selenium  
**Ambiente de desenvolvimento:** Harness Antigravity (agentes de IA) + repositório GitHub  

---

## 1. Visão Geral do Produto

### 1.1 Objetivo
Desenvolver um bot automatizado capaz de **aumentar visualizações (views) e tempo de exibição (watch time)** de vídeos ou canais do YouTube selecionados, simulando comportamento de usuários reais o mais próximo possível, com o menor risco possível de detecção, remoção de vídeos ou banimento da conta.

### 1.2 Problema
Criadores de conteúdo enfrentam dificuldade em gerar tráfego inicial e retenção orgânica. O bot visa fornecer uma ferramenta controlável, configurável e extensível para simular visualizações e tempo de watch de forma programática, com foco em:

- Contagem válida de views (≥ 30 segundos de reprodução, preferencialmente mais).
- Aumento de watch time.
- Manutenção de sessões longas sem interrupção pelo diálogo “Continuar assistindo?” / “Video paused. Continue watching?”.

### 1.3 Escopo Inicial (MVP)
- Sem uso de proxy (planejado para fase futura).
- Controle de navegador real (Chrome/Chromium) via Playwright ou Selenium.
- Suporte a **vídeo único** ou **lista de vídeos de um canal**.
- Clique automático no botão “Continuar assistindo” / “Continue watching”.
- Tempos de watch configuráveis e randomizados.
- Execução em múltiplas instâncias/abas (limitado pelo hardware local).
- Configuração via arquivo `.env` / CLI / YAML.
- Logs estruturados e métricas básicas de sessão.

### 1.4 Fora de Escopo (MVP)
- Proxies (residenciais, datacenter, mobile).
- Contas Google logadas / cookies de login (pode ser adicionado depois).
- Likes, comentários, inscrições ou qualquer engajamento além de view + watch time.
- Interface gráfica web completa (apenas CLI + logs no MVP).
- Deploy em nuvem massivo.
- Bypass agressivo de CAPTCHA / sistemas anti-bot avançados.

---

## 2. Aviso Legal e de Risco (obrigatório)

> **Atenção:** O uso de bots para inflar artificialmente views, watch time ou qualquer métrica de engajamento viola os [Termos de Serviço do YouTube](https://www.youtube.com/static?template=terms) e a política de Fake Engagement.  
> Possíveis consequências: invalidação de views, strikes, remoção de vídeos, restrição de monetização ou banimento da conta.  
> Este projeto é desenvolvido **apenas para fins educacionais, de pesquisa, testes de carga e estudo de automação de navegadores**. O usuário é o único responsável pelo uso.

O PRD e o código devem manter este disclaimer em destaque no README e no início da execução.

---

## 3. Objetivos e Métricas de Sucesso

| Objetivo | Métrica de Sucesso (MVP) |
|----------|--------------------------|
| Gerar views válidas | ≥ 80% das sessões com watch ≥ 30s são contabilizadas (observação manual no Analytics) |
| Aumentar watch time | Tempo médio de sessão configurável (ex.: 60–180s) com variação aleatória |
| Evitar detecção óbvia | Sem bloqueio imediato de IP local em testes de baixo volume (≤ 20 sessões/hora) |
| Robustez | Taxa de falha de sessão < 15% (timeout, elemento não encontrado, crash) |
| “Continuar assistindo” | 100% dos diálogos detectados são clicados com sucesso |
| Facilidade de uso | Execução com 1 comando após configuração mínima |

---

## 4. Personas e Casos de Uso

### Persona principal
- Desenvolvedor / criador de conteúdo que deseja testar automação de navegador e estudar o comportamento do player do YouTube.

### Casos de uso principais
1. **Watch de vídeo único**  
   Usuário informa URL + tempo de watch + número de repetições → bot abre N instâncias e assiste.

2. **Watch de canal**  
   Usuário informa URL do canal → bot coleta lista de vídeos recentes → distribui sessões entre eles.

3. **Sessão longa contínua**  
   Bot mantém o vídeo rodando, trata anúncios skippable quando possível e clica em “Continuar assistindo” sempre que aparecer.

4. **Modo teste / dry-run**  
   Execução com poucos ciclos e logs detalhados para validação.

---

## 5. Requisitos Funcionais

### RF-01 — Configuração de alvo
- Aceitar URL de vídeo (`youtube.com/watch?v=...` ou `youtu.be/...`).
- Aceitar URL de canal e opcionalmente quantidade máxima de vídeos a processar.
- Permitir lista de URLs via arquivo texto/CSV.

### RF-02 — Controle de navegador
- Utilizar Playwright (preferencial) ou Selenium.
- Suportar modo headful (visível) e headless.
- Abrir múltiplas instâncias / contextos / abas em paralelo (configurável).
- Preferir Chromium/Chrome.

### RF-03 — Reprodução de vídeo
- Navegar até a URL.
- Aceitar cookies / consentimento quando necessário (botão “Aceitar tudo” / “Accept all”).
- Iniciar reprodução (clique no play ou via JavaScript no elemento `<video>`).
- Garantir que o vídeo está de fato tocando (verificar `paused === false` e `currentTime` avançando).

### RF-04 — Tempo de watch
- Tempo mínimo e máximo configuráveis (ex.: `min_watch=45`, `max_watch=180`).
- Randomização por sessão.
- Opção de assistir até o final do vídeo ou até um percentual (ex.: 70%).
- Pausas aleatórias curtas (simulação de comportamento humano) — opcional no MVP.

### RF-05 — Diálogo “Continuar assistindo”
- Detectar o popup do YouTube:
  - Textos: “Continuar assistindo?”, “Continue watching?”, “Video paused. Continue watching?”.
  - Seletores comuns: botões com texto correspondente ou elementos do player de inatividade.
- Clicar automaticamente no botão afirmativo.
- Re-tentar periodicamente (polling a cada 5–15s) durante toda a sessão.
- Logar cada ocorrência.

### RF-06 — Tratamento de anúncios (básico)
- Detectar e clicar em “Pular anúncio” / “Skip Ad” quando disponível.
- Não bloquear a sessão caso o anúncio não seja skippable.

### RF-07 — Múltiplas sessões
- Executar N workers em paralelo (limitado por CPU/RAM).
- Cada worker independente (próprio contexto de navegador).
- Atraso aleatório entre o início de cada worker.

### RF-08 — Logging e métricas
- Log por sessão: URL, início, fim, duração efetiva, se clicou em “Continuar assistindo”, erros.
- Contador global de sessões concluídas com sucesso.
- Saída em console + arquivo (JSON Lines ou texto).

### RF-09 — Configuração
- Arquivo `.env` e/ou `config.yaml`.
- Parâmetros CLI para override.
- Valores padrão sensatos para testes.

### RF-10 — Encerramento limpo
- Tratamento de `SIGINT`/`SIGTERM`.
- Fechar todos os navegadores abertos.
- Salvar relatório final da execução.

---

## 6. Requisitos Não-Funcionais

| ID | Requisito | Detalhe |
|----|-----------|---------|
| RNF-01 | Performance | Suportar pelo menos 5–10 instâncias simultâneas em máquina com 16 GB RAM |
| RNF-02 | Confiabilidade | Retry com backoff em falhas de rede ou elemento não encontrado |
| RNF-03 | Observabilidade | Logs com timestamp, nível (INFO/WARN/ERROR) e ID de sessão |
| RNF-04 | Extensibilidade | Arquitetura modular para adicionar proxy, fingerprints e login no futuro |
| RNF-05 | Portabilidade | Funcionar em Windows, Linux e macOS |
| RNF-06 | Manutenibilidade | Código limpo, tipado (type hints), documentado |
| RNF-07 | Segurança local | Não armazenar credenciais em texto plano no repositório |

---

## 7. Arquitetura Técnica (MVP)

┌─────────────────────────────────────────────────────────┐
│                      CLI / Entry Point                   │
│              (main.py + argparse / typer)                │
└──────────────────────────┬──────────────────────────────┘
│
┌──────────────────────────▼──────────────────────────────┐
│                   Config Loader                          │
│              (.env + YAML + defaults)                    │
└──────────────────────────┬──────────────────────────────┘
│
┌──────────────────────────▼──────────────────────────────┐
│                 Session Orchestrator                     │
│     (gerencia pool de workers, filas, limites)           │
└─────────────┬─────────────────────────────┬─────────────┘
│                             │
┌──────────▼──────────┐       ┌──────────▼──────────┐
│   Browser Worker 1  │  ...  │   Browser Worker N  │
│  (Playwright ctx)   │       │  (Playwright ctx)   │
└──────────┬──────────┘       └──────────┬──────────┘
│                             │
└─────────────┬───────────────┘
│
┌─────────────▼─────────────┐
│   YouTube Page Handler    │
│ - play / pause            │
│ - skip ad                 │
│ - continue watching       │
│ - watch timer             │
└───────────────────────────┘

### Tecnologias recomendadas
- **Linguagem:** Python 3.10+
- **Automação:** Playwright (preferencial por melhor suporte a contextos isolados e async) ou Selenium + undetected-chromedriver
- **Config:** `python-dotenv` + `PyYAML` ou `pydantic-settings`
- **CLI:** `typer` ou `argparse`
- **Logs:** `logging` + `structlog` (opcional)
- **Paralelismo:** `asyncio` (Playwright async) ou `concurrent.futures` / `multiprocessing`

### Referências de repositórios para adaptação
- https://github.com/msc2020/bot-youtube (Selenium simples, múltiplas janelas)
- https://github.com/y-t-bot/youtube-viewbot (Playwright/Selenium, .env, Docker)
- Ideias de comportamento humano e randomização presentes em projetos semelhantes da comunidade
- Extensões/conceitos de auto-click em “Continue watching” (ex.: lógica de polling de elementos)

---

## 8. Fluxo Principal de uma Sessão

1. Carregar configuração.
2. Criar contexto de navegador (user-agent padrão ou levemente randomizado).
3. Navegar para a URL do vídeo.
4. Tratar consentimento de cookies (se presente).
5. Aguardar player pronto.
6. Iniciar reprodução.
7. Loop de monitoramento até atingir o tempo de watch:
   - Verificar se o vídeo está tocando.
   - Clicar em “Skip Ad” se disponível.
   - Clicar em “Continuar assistindo” se o diálogo aparecer.
   - Registrar progresso.
8. Encerrar contexto e reportar resultado da sessão.

---

## 9. Roadmap

### Fase 0 — Setup (1–2 dias)
- Criar repositório GitHub.
- Estrutura de pastas, `.gitignore`, README com disclaimer.
- Configuração do Harness Antigravity + agentes.
- Dependências básicas (Playwright instalado).

### Fase 1 — MVP (1–2 semanas)
- CLI funcional.
- Watch de vídeo único com tempo configurável.
- Clique em “Continuar assistindo”.
- Múltiplos workers locais (sem proxy).
- Logs e relatório simples.

### Fase 2 — Robustez
- Coleta de vídeos de canal.
- Melhor tratamento de anúncios e overlays.
- Randomização de timings e user-agent.
- Testes automatizados de smoke.

### Fase 3 — Proxy & Stealth (futuro)
- Suporte a proxies HTTP/SOCKS.
- Rotação de fingerprints.
- Perfis de navegador isolados.
- Opção de cookies/login (avançado e de alto risco).

### Fase 4 — Operação
- Docker.
- Dashboard simples de monitoramento (opcional).
- Limites de rate e cooldown configuráveis.

---

## 10. Estrutura de Repositório Sugerida

youtube-view-watch-bot/
├── README.md                 # Disclaimer + instruções
├── PRD.md                    # Este documento
├── .env.example
├── config.example.yaml
├── requirements.txt
├── pyproject.toml            # opcional
├── src/
│   ├── init.py
│   ├── main.py
│   ├── config.py
│   ├── orchestrator.py
│   ├── browser/
│   │   ├── playwright_worker.py
│   │   └── selenium_worker.py   # opcional
│   ├── youtube/
│   │   ├── player.py
│   │   ├── continue_watching.py
│   │   └── ads.py
│   └── utils/
│       ├── logger.py
│       └── helpers.py
├── tests/
├── scripts/
└── docs/

---

## 11. Critérios de Aceite do MVP

- [ ] É possível rodar `python -m src.main --url <VIDEO_URL> --workers 3 --min-watch 40 --max-watch 90` e obter 3 sessões concluídas.
- [ ] O diálogo “Continuar assistindo” / “Continue watching” é detectado e clicado automaticamente.
- [ ] Logs mostram duração real de cada sessão.
- [ ] Navegadores são fechados corretamente ao final ou ao interromper (Ctrl+C).
- [ ] README contém disclaimer claro e instruções de instalação.
- [ ] Código utiliza Playwright (ou Selenium) de forma modular.
- [ ] Não há dependência de proxy no MVP.

---

## 12. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Violação dos ToS do YouTube | Alto (ban/strikes) | Disclaimer + volume baixo + apenas fins educacionais |
| Detecção por fingerprint/IP | Médio | Sem proxy no MVP → volume muito controlado; preparar extensão futura |
| Mudança de seletores do YouTube | Médio | Seletores flexíveis + fallbacks por texto |
| Alto consumo de recursos | Médio | Limite de workers + modo headless |
| Views não contabilizadas | Médio | Garantir ≥ 30s reais de reprodução e player ativo |

---

## 13. Integração com Harness Antigravity

- O repositório será conectado ao Harness Antigravity.
- Agentes de IA auxiliarão em:
  - Geração e refatoração de código.
  - Criação de testes.
  - Análise de seletores quebrados.
  - Documentação contínua.
- Branches de feature por RF.
- Pull Requests revisados com auxílio dos agentes antes do merge na `main`.

---

## 14. Próximos Passos Imediatos

1. Criar o repositório no GitHub.
2. Commitar este PRD (`PRD.md`) e o README inicial com disclaimer.
3. Configurar ambiente Python + Playwright no Harness Antigravity.
4. Implementar o esqueleto do CLI e do worker de uma sessão.
5. Implementar o handler do “Continuar assistindo”.
6. Validar com 1–3 workers em vídeo de teste de propriedade do usuário.

---

**Documento mantido por:** Equipe do projeto  
**Última atualização:** 07/10/2026