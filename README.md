# PalpitePro Bot

## Visão Geral

O PalpitePro Bot é um bot para Telegram projetado para fornecer análises estatísticas detalhadas e previsões de probabilidade para partidas de futebol. O objetivo principal é auxiliar usuários a tomarem decisões mais informadas em apostas esportivas, processando dados históricos, estatísticas de times e odds de mercado.

O bot recebe uma solicitação do usuário via mensagem no Telegram, contendo os times e a liga da partida desejada. Em seguida, ele consulta a API-Football para obter dados relevantes, processa essas informações usando modelos estatísticos (como a distribuição de Poisson Bivariada) e retorna um relatório completo com probabilidades para diversos mercados de apostas, além de uma sugestão de "Melhor Aposta" baseada na detecção de valor (Value Bet).

Este projeto foi desenvolvido com base em um Documento de Requisitos do Produto (PRD) detalhado, focando na entrega de um núcleo analítico robusto e na integração com o Telegram para fácil acesso do usuário.

## Funcionalidades Implementadas

Até o momento, o PalpitePro Bot implementa as seguintes funcionalidades:

1.  **Integração com Telegram:**
    *   Recebe mensagens de usuários via Telegram.
    *   Responde aos comandos `/start` e `/help` com instruções de uso.
    *   Processa mensagens de texto no formato `Time Casa x Time Fora, Liga [, Season=AAAA] [, Country=NomePais]`.
    *   Envia relatórios de análise formatados em HTML de volta para o chat do usuário.
    *   Utiliza a biblioteca `python-telegram-bot` para a interação.

2.  **Interação com API-Football:**
    *   Busca IDs de times e ligas com base nos nomes fornecidos.
    *   Obtém estatísticas detalhadas das equipes para a temporada e liga especificadas.
    *   Busca o ID do próximo confronto (fixture) entre os times.
    *   Obtém odds de apostas para o confronto (se disponível e `fixture_id` encontrado) de um bookmaker específico (padrão: Bet365).
    *   Busca histórico de confrontos diretos (H2H) - *atualmente não utilizado nos cálculos principais, mas disponível*.
    *   Implementa tratamento de erros para falhas comuns da API (chave inválida, limite de plano, recurso não encontrado).

3.  **Núcleo de Análise (`analysis.py`):**
    *   **Modelo de Poisson Bivariado:** Calcula as taxas esperadas de gols (lambda) para cada time com base em suas forças de ataque e defesa (derivadas das estatísticas da API).
    *   **Cálculo de Probabilidades:**
        *   Resultado Final (1X2)
        *   Ambas Marcam (BTTS - Sim/Não)
        *   Over/Under Gols (para múltiplos limites, ex: 0.5, 1.5, 2.5, 3.5)
        *   Placar Exato (os mais prováveis)
        *   Handicap Asiático (para múltiplas linhas)
        *   Total de Cantos (Over/Under, baseado em médias da API ou padrões)
        *   Intervalo/Final (HT/FT - *implementação simplificada*)
    *   **Detecção de Value Bet:** Compara as probabilidades calculadas com as odds obtidas da API para identificar apostas com valor esperado positivo.
    *   **Sugestão de Melhor Aposta:** Seleciona e apresenta a aposta com o maior valor detectado (se houver).

4.  **Logging:** Sistema básico de logging implementado em todos os módulos para rastrear a execução e facilitar a depuração.

## Estrutura do Projeto

O código está organizado da seguinte forma:

```
/PalpitePro_bot
|-- src/
|   |-- __init__.py
|   |-- main.py         # Ponto de entrada, lógica do bot Telegram
|   |-- api_handler.py  # Funções para interagir com a API-Football
|   |-- analysis.py     # Funções de cálculo e análise estatística
|-- requirements.txt    # Dependências Python do projeto
|-- Readme.md           # Este arquivo
```

*   **`main.py`**: Responsável por inicializar o bot do Telegram, definir os handlers de comando e mensagem, chamar o `api_handler` para buscar dados, invocar o `analysis` para processá-los e formatar/enviar a resposta ao usuário.
*   **`api_handler.py`**: Contém todas as funções que interagem diretamente com os endpoints da API-Football (buscar times, ligas, estatísticas, odds, H2H). Inclui funções auxiliares para processar os dados brutos da API e calcular métricas como forças de ataque/defesa e médias de cantos.
*   **`analysis.py`**: Abriga o núcleo matemático e estatístico. Contém as implementações dos modelos (Poisson), as funções para calcular probabilidades para cada mercado de aposta e a lógica para detecção de valor.
*   **`requirements.txt`**: Lista todas as bibliotecas Python necessárias para executar o projeto.

## Tecnologias Utilizadas

*   **Linguagem:** Python 3.11
*   **Bibliotecas Principais:**
    *   `python-telegram-bot`: Para interagir com a API do Telegram.
    *   `requests`: Para realizar chamadas HTTP à API-Football.
    *   `pandas`: Utilizado internamente em algumas lógicas de manipulação de dados (embora não explicitamente visível nas funções finais).
    *   `scipy`: Utilizado para a função de distribuição de Poisson (`scipy.stats.poisson`).
*   **API Externa:** API-Football (v3.football.api-sports.io)

## Configuração

Para configurar e executar o bot localmente:

1.  **Clone o Repositório (se aplicável):**
    ```bash
    git clone <url_do_repositorio>
    cd PalpitePro_bot
    ```
2.  **Crie um Ambiente Virtual (Recomendado):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```
3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure as Variáveis de Ambiente:**
    Crie um arquivo `.env` na raiz do projeto ou configure as variáveis diretamente no seu sistema:
    ```
    TELEGRAM_BOT_TOKEN="SEU_TOKEN_AQUI"
    API_FOOTBALL_KEY="SUA_CHAVE_API_FOOTBALL_AQUI"
    ```
    *   `TELEGRAM_BOT_TOKEN`: Obtenha conversando com o @BotFather no Telegram.
    *   `API_FOOTBALL_KEY`: Obtenha registrando-se no site da API-Football (api-sports.io).

5.  **Execute o Bot:**
    ```bash
    python src/main.py
    ```
    O bot começará a escutar por mensagens no Telegram.

## Como Usar

1.  Encontre seu bot no Telegram (o nome que você definiu com o BotFather).
2.  Envie o comando `/start` para ver a mensagem de boas-vindas.
3.  Envie uma mensagem com os detalhes da partida no formato:
    `Time Casa x Time Fora, Nome da Liga`
    *   Exemplo: `Manchester City x Liverpool, Premier League`
4.  Opcionalmente, especifique a temporada e o país (útil se houver ligas com nomes iguais ou para dados históricos):
    `Time Casa x Time Fora, Liga, Season=AAAA, Country=NomePais`
    *   Exemplo: `Flamengo x Palmeiras, Brasileirão Série A, Season=2023, Country=Brazil`
5.  Aguarde alguns segundos enquanto o bot busca os dados e realiza a análise.
6.  O bot responderá com um relatório detalhado contendo as probabilidades estimadas para diversos mercados e a sugestão de "Melhor Aposta".

## Deployment

Para que o bot funcione continuamente, ele precisa ser hospedado em um servidor ou plataforma na nuvem.

*   **Método Atual:** O `main.py` utiliza `application.run_polling()`, que mantém uma conexão aberta com o Telegram. Isso é adequado para rodar localmente ou em um VPS dedicado.
*   **Método Recomendado para Serverless/PaaS (Webhook):** Para plataformas como AWS Lambda ou Heroku, é mais eficiente usar Webhooks. Isso envolve:
    1.  Adaptar `main.py` para ser um aplicativo web (usando Flask, FastAPI, etc.) que recebe requisições POST do Telegram.
    2.  Configurar um endpoint HTTPS público para o aplicativo.
    3.  Registrar esse endpoint como webhook no Telegram usando o BotFather ou uma chamada de API.
    4.  Empacotar o código e dependências adequadamente para a plataforma escolhida (ex: ZIP para Lambda).
*   **Plataformas Sugeridas:**
    *   **AWS Lambda:** Custo-benefício para bots, paga por execução. Requer adaptação para webhooks e empacotamento.
    *   **VPS (EC2, DigitalOcean, etc.):** Controle total, mas exige gerenciamento do servidor. Pode rodar com `run_polling` usando `supervisor` ou `systemd`.
    *   **PaaS (Heroku, Google App Engine):** Simplifica o deployment, mas pode ter custos associados. Geralmente funciona melhor com webhooks.
*   **Variáveis de Ambiente:** Independentemente da plataforma, as chaves (`TELEGRAM_BOT_TOKEN`, `API_FOOTBALL_KEY`) **DEVEM** ser configuradas como variáveis de ambiente seguras, e não diretamente no código.

## Limitações e Próximos Passos

*   **Limitações Atuais:**
    *   O modelo HT/FT é uma simplificação e pode ser menos preciso.
    *   A precisão do modelo de Cantos depende da qualidade dos dados médios da API.
    *   A disponibilidade de dados (estatísticas, odds) depende do plano da API-Football e da cobertura da liga/temporada.
    *   A busca por `fixture_id` e odds pode falhar se o jogo estiver muito distante ou se o bookmaker padrão não cobrir.
*   **Próximos Passos Possíveis:**
    *   **Deployment:** Escolher e implementar uma estratégia de deployment (Lambda, VPS, etc.).
    *   **Refinamento dos Modelos:** Melhorar os modelos HT/FT e Cantos, talvez incorporando mais dados ou abordagens diferentes.
    *   **Interface do Usuário:** Adicionar botões interativos no Telegram para facilitar a seleção de mercados ou opções.
    *   **Histórico de Análises:** Salvar análises realizadas para referência futura ou acompanhamento de desempenho.
    *   **Monitoramento e Alertas:** Implementar monitoramento mais robusto no ambiente de produção.
    *   **Testes Unitários e de Integração:** Adicionar testes automatizados para garantir a qualidade do código.

---
*Documentação gerada em [Data Atual]*

