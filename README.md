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
├── models.py              Cliente, Endereco, Evento e os enums do domínio
├── schemas.py             dataclasses que a UI envia para o repository
├── repository/
│   ├── clientes.py        listar, buscar, criar, atualizar, excluir clientes
│   └── eventos.py         CRUD de eventos, filtros, histórico, mudança de status
└── ui/
    ├── estilo.py          tema claro: paleta, fontes e folha de estilo
    ├── main_window.py     janela com as abas Clientes e Agenda
    ├── clientes_tab.py    lista, ficha do cliente, endereços e histórico
    ├── eventos_tab.py     calendário do mês e a folha do dia
    ├── calendario.py      a grade do mês
    ├── evento_dialog.py   diálogo de inclusão e edição de um serviço
    ├── widgets.py         etiquetas, botões segmentados, tabelas e endereço
    └── mensagens.py       caixas de erro e confirmação
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

## Visual

O app tem tema claro próprio e não acompanha o tema escuro do sistema: a
paleta, as fontes e a folha de estilo ficam todas em `app/ui/estilo.py`, e
`aplicar_tema()` é chamado em `main.py` antes de abrir a janela. A direção é
papel de agenda de escritório — fundo branco, pautas finas, azul-caneta como
acento e laranja-carimbo para as retiradas. Texto em **Inter**; **JetBrains
Mono** só nos números e nas etiquetas. Se alguma dessas fontes não estiver
instalada, o Qt cai para a fonte padrão do sistema sem quebrar nada.

## Notas técnicas

- Os enums são gravados no banco pelo **nome** (`PF`, `COLETA`, `MANHA`), e o
  valor do enum é o rótulo em português mostrado na tela.
- A sessão usa `expire_on_commit=False`, então os objetos continuam legíveis
  depois que a sessão fecha — é o que permite montar as telas com eles.
- Cada ação da interface abre e fecha sua própria sessão (`session_scope`), com
  commit no fim e rollback em caso de erro.
- Não há Alembic: as tabelas são criadas por `create_all`. Se o modelo mudar
  depois que já houver dados em produção, o ideal é adicionar migrações.
