# Peso_RFID — Contexto do Projeto

## Propósito

Sistema de automação e dashboard desenvolvido por **Guilherme Prado** para a **São Geraldo Service**, empresa de gestão de enxoval hospitalar. Este projeto monitora **peso de lavanderia** (limpo, sujo e relave) de todas as unidades/clientes, com foco em dar visibilidade diária ao diretor da empresa sobre volume processado e qualidade operacional (índice de relave).

Projeto **irmão** do [Robo_RFID](../Robo_RFID) (que trata de evasão de enxoval via RFID), mas mantido em pasta e repositório Git separados — sistemas e times de dados independentes, mesmo compartilhando o mesmo sistema legado como fonte.

## Google Sheets

- **Nome:** `Base_Dados_Peso`
- **Sheet ID:** `1JXvEHzdD8nyrtA19b9MBKHe_0DCjfteaEuCQ_rrtIGw`
- **Conta de serviço com acesso:** `robo-rfid@robo-rfid.iam.gserviceaccount.com` (mesma do Robo_RFID — reaproveitada por decisão de Guilherme; ver seção de aprendizados sobre o trade-off)
- **Aba `Peso_Bruto`:** já criada, com cabeçalho `Data Extração | Cliente | Data | Peso Limpo (kg) | Peso Sujo (kg) | Peso Relave (kg)`
- **Nota técnica:** a planilha precisa ser criada manualmente pelo usuário no Google Sheets (não pela conta de serviço) e depois compartilhada com o e-mail acima como Editor — contas de serviço têm cota de armazenamento no Drive praticamente zerada e não conseguem criar arquivos novos via API (`gspread.Client.create()` falha com `403 Drive storage quota exceeded`).

## Pipeline (planejado, mesmo modelo do Robo_RFID)

```
Sistema legado ASP.NET WebForms (sistemasaogeraldo.com.br)
  → cliente "TODAS" → menu "Lavanderia" → "Controle Operacional - Lavanderia"
    ↓ Selenium (scraping)
Google Sheets (armazenamento intermediário — aba Peso_Bruto, log histórico)
    ↓ refinador_peso.py (deduplica por Cliente + Data, mantém o mais recente)
Google Sheets (abas agregadas para o dashboard)
    ↓ Publicação como CSV (gviz/pub)
Dashboard estático (index.html) no GitHub Pages
```

## Arquivos principais

- **`peso.py`** ✅ **(criado e validado)** — scraper Selenium principal. Loga no sistema, garante unidade "TODAS" selecionada, e navega direto (via URL, sem cliques de menu) por `ListagemLavanderia.aspx?dia=DD/MM/AAAA` para cada dia do mês corrente (1 até hoje). Cada página já lista peso limpo/sujo/relave de **todos os clientes de uma vez** — não precisa iterar cliente por cliente como o `robo.py`. Grava tudo em `Peso_Bruto` via `append_rows`. Testado com trava de 1 dia: 137 clientes capturados e valores conferidos batendo com a tela real.
- **`refinador_peso.py`** (a criar) — lê a aba `Peso_Bruto` (log bruto, cresce a cada rodada), deduplica por `Cliente + Data` (mantém a extração mais recente — corrige valores retroativos), gera as abas agregadas que o dashboard consome.
- **`geral_peso.bat`** (a criar) — orquestrador (`peso.py` + `refinador_peso.py`), a ser agendado no Windows Task Scheduler (horário a definir — sugestão: rodar após o fechamento do dia anterior, ex. 06:00–07:00, já que o cálculo do "dia anterior" depende do dado do dia anterior estar completo).
- **`index.html`** (a criar) — dashboard "Mapa Controle de Peso", deploy manual (mesmo fluxo do Robo_RFID: copiar conteúdo → colar no editor web do GitHub).

## Navegação no sistema legado (mapeada e confirmada — crítico, não é a mesma tela do Robo_RFID)

1. Login com `USUARIO_RFID` / `SENHA_RFID` (mesmas credenciais do Robo_RFID, mesmo sistema).
2. Combo de unidades (`ctl00$ComboUnidade`) já vem com **"TODAS"** selecionado por padrão após login — `peso.py` reforça a seleção por segurança, mas não precisa trocar cliente por cliente como o `robo.py`.
3. Tela real é `ListagemLavanderia.aspx` (menu LAVANDERIA → "Controle Operacional - Lavanderia"). Ela é acessível **direto por URL** com querystring `?dia=DD/MM/AAAA` — não precisa clicar em nada, mesmo padrão de navegação direta usado no `robo.py` para Evasão.
4. Cada requisição de um dia específico retorna, na tabela `id="tabpedidos"`, **uma linha por cliente** com os dados **daquele dia** (não do mês inteiro — o mês inteiro só aparece agregado nas seções de resumo do topo da página, que `peso.py` ignora).
5. **Mapeamento de colunas confirmado (índice 0-based) na tabela `#tabpedidos`:** `0`=Cliente, `1`=R.SUJA (peso sujo), `2`=R.LIMPA (peso limpo), `3`=RS×RL, `4`=% Saldo, `5`=Gaiolas, `6`=(vazia/spacer), `7`=RELAVAGEM (peso relave), `8`=% Relavagem, demais colunas são de faturamento/meta (não usadas). A primeira linha da tabela vem vazia (spacer do `floatThead`) e a última é sempre `TOTAL` — `peso.py` pula ambas identificando por nome do cliente vazio ou `"TOTAL"`.
6. Números vêm no padrão BR **sem separador de milhar** nesses campos (ex: `"246476,3"`), então o parse é só `replace(',', '.')` — mas `parse_num()` em `peso.py` também remove `.` por segurança, caso o formato mude.
7. Dias futuros (sem dado ainda) retornam a tabela normalmente, só que com zeros — não há erro/exceção, então não precisa tratamento especial além do range `1..hoje.day`.

## Modelo de dados (Peso_Bruto — aba de log histórico bruto)

Long format, uma linha por `Cliente + Data`, igual ao padrão de `Dados_Brutos` do Robo_RFID:

| Coluna | Descrição |
|---|---|
| `Data Extração` | Timestamp da rodada do robô (`DD/MM/AAAA HH:MM`) |
| `Cliente` | Nome da unidade |
| `Data` | Dia a que o peso se refere (`DD/MM/AAAA`) |
| `Peso Limpo (kg)` | Peso limpo do dia |
| `Peso Sujo (kg)` | Peso sujo do dia (**métrica financeira** — é o peso sujo que gera receita) |
| `Peso Relave (kg)` | Peso de relave do dia |

**Regra de negócio crítica**: `% Relave = (Peso Relave / Peso Sujo) × 100`. Exemplo: 100kg de relave sobre 1000kg de peso sujo = 10% de relave. **Meta da empresa: % Relave ≤ 3%.**

`refinador_peso.py` deduplica esse log por `Cliente + Data` (mantém o registro mais recente), preservando histórico de meses fechados indefinidamente — nada é apagado, cada rodada nova só atualiza os dias já existentes e adiciona os novos.

## Dashboard — especificação de visualização

### Cabeçalho
- Título: **"MAPA CONTROLE DE PESO"**
- Indicador do mês de referência (ex: "Julho/26")

### Cards de resumo (topo)
Uma linha com **4 cards**, todos baseados em **Peso Sujo** (métrica financeira):
1. **Peso Sujo — Mês Atual**: soma do peso sujo de todas as unidades no mês corrente.
2. **Peso Sujo — Mês Anterior**: mesmo cálculo, mês -1 (comparação).
3. **Peso Sujo — Retrasado**: mesmo cálculo, mês -2 (comparação, para ver tendência de 3 meses).
4. **Peso Sujo — Dia Anterior**: soma do peso sujo de todas as unidades no **dia anterior** (não o dia atual — o dia atual pode estar com unidades ainda não preenchidas pelo sistema, dependendo do horário em que o robô roda).

### Divisão do mês em 4 janelas semanais
- O mês corrente é dividido em 4 blocos de ~7 dias corridos (dia 1-7, 8-14, 15-21, 22-fim), não por dia da semana.
- Cada bloco mostra o total de peso (sujo) do período.
- Comparação direta de cada bloco com o **bloco equivalente do mês anterior** (mesma janela de dias), para saber se o ritmo está subindo, estável ou caindo.

### Janela de 7 dias — detalhamento por cliente
- Tabela com **um dia por vez** (não os 7 dias lado a lado) — navegação por abas ou setinhas ‹ › para trocar de dia, no mesmo espírito do navegador de setores do Robo_RFID.
- Colunas: **Cliente | Peso Limpo | Peso Sujo | Peso Relave | % Relave**.
- Linha de **TOTAL** no rodapé da tabela, somando cada coluna (limpo, sujo, relave) e recalculando o % relave total do dia (não é a soma das porcentagens individuais — é total relave / total sujo do dia).
- Cor do % Relave: verde se ≤ 3% (dentro da meta), vermelho/amarelo se acima (a definir a escala exata de cores quando formos implementar — seguir o mesmo espírito das cores de evasão do Robo_RFID).

## Identidade visual

Mesmo padrão do Robo_RFID, por continuidade de marca:
- Azul: `#1a6fb5`
- Verde: `#3da84a`
- Fontes: Montserrat + Inter
- Mesma estrutura de cards, tabelas e badges (reaproveitar CSS do `index.html` do Robo_RFID como base).

## Stack

- Python, Selenium (scraping ASP.NET), Google Sheets API (`gspread`)
- GitHub Pages (hospedagem estática do dashboard) — **repositório separado** do Robo_RFID
- Windows Task Scheduler (automação diária, agendamento a definir)

## Aprendizados herdados do Robo_RFID (aplicam-se aqui também)

- **Sempre usar `value_input_option='RAW'`** ao escrever no Google Sheets.
- **Parsing de CSV deve ser posicional (por índice) ou por header único** — nunca por nome de coluna duplicada.
- **Caminhos**: sempre usar `os.path.join(DIR, 'credenciais.json')`.
- **Timeout de carregamento de página**: 120s (site ASP.NET é lento).
- **Padrão de teste**: rodar com 1 cliente/dia limitado antes de soltar em produção total, com uma trava de teste comentada explicitamente (`# 🔒 TRAVA DE TESTE`).
- **Sempre entregar o conteúdo completo do arquivo, pronto para colar** — nunca snippets parciais ou diffs, já que o deploy do dashboard é manual via Notepad + editor web do GitHub.
- `toNum()` no JS: nunca reprocessar um valor que já é `number` como se fosse string de planilha (causa bug de ponto flutuante) — sempre checar `typeof v === 'number'` antes.

## Estado atual

### Concluído
- Definição de escopo e navegação no sistema legado.
- Modelo de dados (`Peso_Bruto`) definido.
- Especificação completa da visualização do dashboard.
- `CLAUDE.md` inicial criado.
- `credenciais.json` e `.env` copiados do Robo_RFID (mesma conta de serviço, mesmo login do sistema).
- `.gitignore` criado (protege `.env` e `credenciais.json` de irem pro Git).
- Planilha `Base_Dados_Peso` criada manualmente por Guilherme, compartilhada com a conta de serviço, aba `Peso_Bruto` configurada com cabeçalho.
- `peso.py` escrito e testado com trava de 1 dia (dia 01/07/2026): 137 clientes capturados, valores conferidos batendo com a tela real do sistema. Trava de teste desativada (comentada) — pronto para rodar a extração completa do mês.

### Pendente / em aberto
- Rodar `peso.py` em produção completa (todos os dias do mês até hoje) para popular `Peso_Bruto` de verdade.
- Escrever `refinador_peso.py`.
- Escrever `index.html` (dashboard).
- Habilitar publicação na web da planilha (Arquivo → Compartilhar → Publicar na Web) quando as abas agregadas existirem.
- Confirmar cor/escala exata do badge de % Relave (verde/amarelo/vermelho) em relação à meta de 3%.
- Confirmar horário ideal de agendamento no Task Scheduler (depende do card "Dia Anterior" ter dado completo).
- Criar repositório Git separado e configurar GitHub Pages para este projeto.
