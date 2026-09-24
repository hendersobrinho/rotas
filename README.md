# Rotas do Motoboy

Sistema desktop para organizar as coletas e retiradas feitas pelo motoboy do
escritório de contabilidade. Guarda o cadastro dos clientes (com endereço
residencial e comercial) e a agenda de eventos ligada a cada um.

- **Interface:** PySide6 (Qt 6)
- **Banco:** PostgreSQL via SQLAlchemy 2.0 (driver `psycopg` 3)

## Requisitos

- Python 3.10 ou superior
- PostgreSQL acessível (local ou em rede)

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie o banco (uma vez só):

```bash
createdb rotas          # ou: psql -c "CREATE DATABASE rotas;"
```

## Configuração

A conexão vem de variáveis de ambiente. Copie o modelo e ajuste:

```bash
cp .env.example .env
```

| Variável | Para que serve | Padrão |
| --- | --- | --- |
| `ROTAS_DATABASE_URL` | URL completa; quando presente, ignora as demais | — |
| `ROTAS_DB_HOST` | Servidor do PostgreSQL | `localhost` |
| `ROTAS_DB_PORT` | Porta | `5432` |
| `ROTAS_DB_NAME` | Nome do banco | `rotas` |
| `ROTAS_DB_USER` | Usuário | `postgres` |
| `ROTAS_DB_PASSWORD` | Senha | vazio |
| `ROTAS_SQL_ECHO` | `1` mostra o SQL gerado no terminal | `0` |

O `.env` é lido automaticamente quando o pacote `python-dotenv` está instalado
(ele está no `requirements.txt`). As variáveis de ambiente do sistema também
funcionam sem `.env`.

## Rodando

```bash
python main.py
```

Na primeira execução as tabelas são criadas automaticamente
(`Base.metadata.create_all`).

## Estrutura

```
main.py                    ponto de entrada: carrega .env, cria tabelas, abre a janela
app/
├── db.py                  URL de conexão, engine, session_scope(), init_db()
├── models.py              as tabelas e os enums do domínio
├── schemas.py             dataclasses que a UI envia para o repository
├── seguranca.py           hash de senha (PBKDF2) e tokens de sessão
├── sessao.py              quem está logado e o token deste computador
├── repository/
│   ├── clientes.py        listar, buscar, criar, atualizar, excluir clientes
│   ├── eventos.py         CRUD de eventos, filtros, histórico, mudança de status
│   ├── tipos_servico.py   cadastro dos tipos
│   ├── solicitantes.py    cadastro de quem pede
│   ├── usuarios.py        contas, autenticação e sessões salvas
│   └── logs.py            gravação e consulta do registro de atividades
└── ui/
    ├── estilo.py          tema claro: paleta, fontes e folha de estilo
    ├── main_window.py     janela com as abas Agenda, Clientes, Painel e Cadastros
    ├── eventos_tab.py     calendário do mês e a folha do dia
    ├── calendario.py      a grade do mês
    ├── evento_dialog.py   diálogo de inclusão e edição de um serviço
    ├── clientes_tab.py    lista, ficha do cliente, endereços e histórico
    ├── login.py           tela de entrada e 'continuar conectado'
    ├── cadastros.py       tipos de serviço, solicitantes e usuários
    ├── registro_tab.py    consulta do registro de atividades
    ├── painel_tab.py      indicadores e gráficos do período
    ├── graficos.py        barras desenhadas com QPainter
    ├── relatorio_pdf.py   emissão do PDF da agenda
    ├── datas.py           datas em português, agrupamento e intervalos
    ├── widgets.py         etiquetas, botões segmentados, tabelas e endereço
    └── mensagens.py       caixas de erro e confirmação
scripts/
└── migrar_tipos_e_solicitantes.py   migração para o formato com cadastros
```

A regra é: `ui/` nunca fala com o banco direto — sempre passa pelo
`repository/`, que por sua vez só conhece `models` e `schemas`.

## Como o sistema funciona

### Clientes

- Tipo **PF** ou **PJ**; o campo *Nome* guarda o nome completo ou a razão social.
- O *apelido / nome social* é o que aparece nas listas e nos combos.
- Cada cliente tem no máximo **um endereço residencial e um comercial** —
  garantido no banco pela constraint `uq_endereco_cliente_tipo`.
- Para dizer que o cliente **não tem** determinado endereço, basta deixar todos
  os campos daquele bloco em branco e salvar: o registro é removido.
- A busca filtra por nome **ou** apelido, sem diferenciar maiúsculas e acentos
  de caixa (`ILIKE`).
- O **histórico** fica na terceira coluna, sempre visível: são os serviços do
  cliente, do mais recente para o mais antigo. Clicar duas vezes numa linha
  abre aquele dia na agenda.
- O histórico pode ser agrupado por **semana**, **mês** ou **ano**. Cada
  período vira uma faixa com o rótulo e a quantidade de serviços; nada é
  escondido, só organizado. A semana começa no domingo, igual ao calendário.

### Entrar no sistema

Na primeira execução não existe usuário nenhum, e a tela de entrada pede para
criar o primeiro — é ele que depois cadastra os outros, na aba Cadastros.

A opção **Continuar conectado neste computador** guarda um token em
`~/.local/share/rotas/sessao.json`, com permissão de leitura só para o seu
usuário do sistema operacional. O token vale 30 dias, e o banco guarda apenas o
hash dele: o arquivo sozinho não revela senha nenhuma. Sair pelo botão no canto
da barra de abas apaga o token dos dois lados e volta para a tela de entrada.
Trocar a senha de alguém encerra todos os "continuar conectado" daquela pessoa.

As senhas ficam como hash PBKDF2-SHA256 com 240 mil iterações e sal por usuário
(`app/seguranca.py`) — nenhuma senha é gravada em texto.

### Cadastros

- **Tipos de serviço**: Coleta e Retirada vêm prontos, e você cria os que quiser
  (*Entrega de guia*, *Malote*...). Cada tipo tem uma cor da paleta, que carrega
  junto um símbolo próprio (● ▲ ■ ◆) — a cor nunca é a única pista. Um tipo em
  uso não pode ser excluído; desmarque *Ativo* para tirá-lo das novas marcações
  sem mexer no histórico.
- **Usuários**: quem entra no sistema. Não dá para excluir a si mesmo nem
  deixar o sistema sem nenhum usuário ativo.
- **Solicitantes**: quem pede o serviço, com o setor. Aparecem prontos na lista
  ao marcar um serviço, e dá para cadastrar na hora, sem sair do diálogo.

### Agenda

A aba abre no **mês inteiro**. Cada dia lista o apelido dos clientes que têm
serviço marcado — azul (●) para coleta, laranja (▲) para retirada, riscado
quando cancelado. Clicar num dia entra nele: a folha do dia mostra os serviços
separados em **manhã** e **tarde**, e o botão *Incluir serviço* já chega com a
data preenchida. Clicar num serviço abre o mesmo diálogo para editar.

- Sempre ligados a um cliente; o endereço é **opcional** e, quando informado,
  precisa ser um dos endereços daquele cliente.
- Serviço **Coleta** ou **Retirada**, com data e período (**Manhã**/**Tarde**).
- *Solicitante* é a pessoa do escritório que pediu o serviço.
- Situação: **Pendente**, **Concluído** ou **Cancelado**, trocada no próprio
  diálogo.
- **Cancelar ≠ Excluir**: mudar a situação para Cancelado mantém o serviço no
  histórico; o botão *Excluir* apaga a linha de vez.
- Excluir um cliente apaga também seus endereços e serviços (a tela avisa
  quantos serão perdidos).
- **Baixa rápida**: cada linha da folha do dia tem um botão redondo na borda
  direita. Um clique marca como concluído; o mesmo botão desfaz.

### Painel

Indicadores e gráficos do período escolhido — **semana**, **mês** ou **ano** —
com as setas navegando de um período a outro: total, pendentes, concluídos e
cancelados; serviços ao longo do período (por dia, ou por mês quando o período
é o ano); por tipo de serviço, cada um na sua cor; e os oito primeiros clientes
e solicitantes. Passar o mouse numa barra mostra o número exato.

### Registro de atividades

Toda inclusão, alteração e exclusão fica registrada, junto com as entradas e
saídas do sistema: quando, quem, o que foi feito e sobre o quê. A aba
**Registro** filtra por usuário, ação, tipo de coisa, texto e período.

O registro só recebe linhas novas — nada é alterado nem apagado por ali. O nome
de quem fez é copiado para a linha, então excluir um usuário não apaga o rastro
do que ele fez.

### PDF da agenda

O botão *Emitir PDF* aparece no cabeçalho do mês e na folha do dia. Sai o dia ou
a semana, em dois formatos:

- **A4**, para imprimir ou mandar por e-mail;
- **Celular**, uma página estreita (95 × 170 mm) que preenche a tela do telefone
  sem precisar de zoom.

Cada serviço sai com quadradinho para marcar, tipo, cliente, endereço completo,
telefone, situação e quem pediu. O PDF é vetorial: amplia sem embaçar.

## Visual

O app tem tema claro próprio e não acompanha o tema escuro do sistema: a
paleta, as fontes e a folha de estilo ficam todas em `app/ui/estilo.py`, e
`aplicar_tema()` é chamado em `main.py` antes de abrir a janela. A direção é
papel de agenda de escritório — fundo branco, pautas finas, azul-caneta como
acento e laranja-carimbo para as retiradas. Texto em **Inter**; **JetBrains
Mono** só nos números e nas etiquetas. Se alguma dessas fontes não estiver
instalada, o Qt cai para a fonte padrão do sistema sem quebrar nada.

## Migração

Nas primeiras versões o tipo de serviço era um ENUM nativo e o solicitante um
texto solto. Quem já tem banco desse formato roda uma vez:

```bash
.venv/bin/python scripts/migrar_tipos_e_solicitantes.py
```

Ele cria as tabelas novas, transforma os valores antigos em cadastro e troca as
colunas por chaves estrangeiras. Pode rodar de novo sem estragar nada — cada
passo confere antes se já foi feito. Em banco novo, não há o que migrar.

As tabelas de usuários, sessões e registro de atividades são criadas sozinhas
por `create_all` na primeira execução — não precisam de script.

## Notas técnicas

- Os enums são gravados no banco pelo **nome** (`PF`, `COLETA`, `MANHA`), e o
  valor do enum é o rótulo em português mostrado na tela.
- A sessão usa `expire_on_commit=False`, então os objetos continuam legíveis
  depois que a sessão fecha — é o que permite montar as telas com eles.
- Cada ação da interface abre e fecha sua própria sessão (`session_scope`), com
  commit no fim e rollback em caso de erro.
- Não há Alembic: as tabelas são criadas por `create_all`, e mudanças de formato
  entram como scripts em `scripts/`.
- A paleta dos tipos de serviço tem **quatro** cores, e não mais: nenhum conjunto
  de cinco cores escuras o bastante para servir de texto passou na separação
  entre todos os pares nas simulações de daltonismo. As quatro escolhidas passam
  em tudo (pior par: ΔE 9,3 em protanopia). O detalhe está comentado em
  `app/ui/estilo.py`.
- Os gráficos do painel são desenhados com `QPainter`, sem dependência de
  biblioteca de gráficos.
