# Rotas do Motoboy

Sistema desktop para organizar as coletas e retiradas feitas pelo motoboy do
escritório de contabilidade. Guarda o cadastro dos clientes (com endereço
residencial e comercial) e a agenda de eventos ligada a cada um.

- **Interface:** PySide6 (Qt 6)
- **Banco:** PostgreSQL via SQLAlchemy 2.0 (driver `psycopg` 3)
- **Planilhas:** openpyxl, para o modelo e a importação de clientes

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
| `ROTAS_DB_TIMEOUT` | Segundos de espera pelo servidor (mínimo 2) | `5` |
| `ROTAS_SQL_ECHO` | `1` mostra o SQL gerado no terminal | `0` |

O `.env` é lido automaticamente quando o pacote `python-dotenv` está instalado
(ele está no `requirements.txt`). As variáveis de ambiente do sistema também
funcionam sem `.env`.

### Preparando o banco

O sistema **não cria o banco nem o usuário** — isso é do PostgreSQL. Ele cria
as tabelas sozinho. Então, no servidor, é só isto, uma vez:

```sql
CREATE USER rotas WITH PASSWORD 'a-senha-que-voce-escolher';
CREATE DATABASE rotas OWNER rotas;
```

**O nome não é fixo.** Banco e usuário podem se chamar o que você quiser; o
que importa é apontar o sistema para eles (`ROTAS_DB_NAME` e `ROTAS_DB_USER`,
ou a tela de Conexão no Windows). `rotas` é só o padrão de quem não informa
nada. O usuário precisa ser dono do banco, ou ter permissão de criar tabelas
nele — é ele que roda o `CREATE TABLE` da primeira execução.

Na primeira vez que o programa abre, então, acontece nesta ordem:

1. conecta no banco e **cria as tabelas** que faltam (`create_all`);
2. como ainda não existe usuário **do sistema**, a tela de entrada pede para
   criar o primeiro — nome, login e senha. Esse é o login do programa, que não
   tem nada a ver com o usuário do PostgreSQL.

Banco em outro computador: libere o acesso de fora no servidor —
`listen_addresses` no `postgresql.conf` e uma linha para a faixa da rede no
`pg_hba.conf`.

## Rodando

```bash
python main.py
```

Na primeira execução as tabelas são criadas automaticamente
(`Base.metadata.create_all`).

## Estrutura

```
main.py                    ponto de entrada: carrega .env, cria tabelas, abre a janela
rotas.spec                 receita do PyInstaller
instalador/rotas.iss       receita do instalador do Windows (Inno Setup)
app/
├── recursos/              logotipo, ícone do programa e as fontes embarcadas
├── caminhos.py            onde ficam configuração, dados e recursos
├── planilha.py            leitura e escrita de .xlsx e .csv
├── importacao_clientes.py colunas da planilha de clientes, modelo e conferência
├── db.py                  URL de conexão, engine, session_scope(), init_db()
├── models.py              as tabelas e os enums do domínio
├── schemas.py             dataclasses que a UI envia para o repository
├── configuracao.py        leitura e gravação da conexão no .env
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
    ├── marca.py           cores da marca, logotipo e ícone do programa
    ├── estilo.py          tema claro: paleta, fontes e folha de estilo
    ├── main_window.py     janela com as abas Agenda, Clientes, Painel e Cadastros
    ├── eventos_tab.py     calendário do mês e a folha do dia
    ├── calendario.py      a grade do mês
    ├── evento_dialog.py   diálogo de inclusão e edição de um serviço
    ├── clientes_tab.py    lista, ficha do cliente, endereços e histórico
    ├── login.py           tela de entrada e 'continuar conectado'
    ├── teclado.py         estado do Caps Lock
    ├── cadastros.py       tipos de serviço, solicitantes e usuários
    ├── registro_tab.py    consulta do registro de atividades
    ├── reagendar.py       "não deu para fazer", remarcação e pendências
    ├── recorrencia_dialog.py  regra de um serviço fixo, com prévia das datas
    ├── conexao_dialog.py  configuração da conexão com o banco
    ├── importar_clientes.py  prévia e gravação da planilha de clientes
    ├── seletor_cliente.py janela de busca de cliente
    ├── seletor_data.py    mini calendário de dia ou semana
    ├── painel_tab.py      indicadores e gráficos do período
    ├── graficos.py        barras desenhadas com QPainter
    ├── relatorio_pdf.py   emissão do PDF da agenda
    ├── datas.py           datas em português, agrupamento e intervalos
    ├── widgets.py         etiquetas, botões segmentados, tabelas e endereço
    └── mensagens.py       caixas de erro e confirmação
testes/
├── comum.py               banco descartável e dados de exemplo
├── teste_interface.py     entrada, conexão, clientes, agenda, cadastros e painel
├── teste_recorrencia.py   regras de repetição e abertura automática
├── teste_enderecos.py     vários endereços por cliente
├── teste_obrigatorios.py  cliente e endereço obrigatórios
├── teste_importacao.py    modelo da planilha, leitura, conferência e gravação
├── teste_pdf.py           logotipo, cores, folha deitada e versão celular
└── rodar.sh               roda tudo num banco de teste
scripts/
├── migrar_tipos_e_solicitantes.py   migração para o formato com cadastros
├── migrar_nao_realizado.py          migração do estado "não realizado"
├── migrar_servicos_fixos.py         migração dos serviços automáticos
├── migrar_varios_enderecos.py       libera vários endereços por cliente
├── gerar_icones.py                  ícone do programa em todos os tamanhos
├── instalar_atalho_linux.py         atalho no menu e na área de trabalho
└── diagnostico_capslock.py          o que cada leitura do Caps Lock responde
```

A regra é: `ui/` nunca fala com o banco direto — sempre passa pelo
`repository/`, que por sua vez só conhece `models` e `schemas`.

## Como o sistema funciona

### Clientes

- Tipo **PF** ou **PJ**; o campo *Nome* guarda o nome completo ou a razão social.
- O *apelido / nome social* é o que aparece nas listas e nos combos.
- Cada cliente tem **quantos endereços precisar**. O botão *Adicionar
  endereço*, no alto do cartão, acrescenta um bloco; o *Remover* de cada um
  tira. Cada endereço tem um tipo (residencial ou comercial) e um **nome** —
  *Matriz*, *Filial Barreiro*, *Depósito* —, que é como ele aparece na hora de
  marcar um serviço e nos relatórios. Dois endereços do mesmo tipo com o mesmo
  nome não passam, senão ninguém os distingue na lista.
- Um bloco deixado inteiramente em branco é ignorado, e um endereço removido da
  tela sai do banco quando você salva.
- A busca filtra por nome **ou** apelido, sem diferenciar maiúsculas e acentos
  de caixa (`ILIKE`).
- A ficha abre **só para leitura**: dá para passear pela lista vendo os dados
  sem risco de mexer em nada. O botão *Editar cliente*, no topo da ficha, é que
  libera os campos — e enquanto você edita, a lista fica travada até salvar ou
  descartar.
- O **histórico** fica na terceira coluna, sempre visível: são os serviços do
  cliente, do mais recente para o mais antigo. Clicar duas vezes numa linha
  abre aquele dia na agenda.
- O histórico pode ser agrupado por **semana**, **mês** ou **ano**. Cada
  período vira uma faixa com o rótulo e a quantidade de serviços; nada é
  escondido, só organizado. A semana começa no domingo, igual ao calendário.

### Importar clientes por planilha

Cadastro em lote, para quem está começando a usar o sistema ou recebeu uma
lista pronta. O botão *Importar planilha*, embaixo de *Novo cliente*, abre a
tela.

**Baixar o modelo.** O primeiro botão da tela gera uma planilha em branco com
todas as colunas do cadastro e uma aba *Como preencher* explicando cada uma.
As colunas de tipo já vêm com lista suspensa, e as células vêm formatadas como
texto — senão o Excel come o zero à esquerda de um CEP.

**Uma linha por cliente.** As primeiras colunas são os dados do cliente (tipo,
nome/razão social, apelido, telefone, observação). Depois vem **um bloco de
colunas para cada endereço** — *Endereço 1 - Tipo*, *Endereço 1 - Nome do
endereço*, *Endereço 1 - Logradouro*... até a observação —, repetido três
vezes. Cliente com mais de três endereços: copie o último bloco, cole no fim e
troque o número para 4. A leitura conta os blocos pelo cabeçalho, não por um
número fixo. Bloco totalmente em branco é ignorado.

O cabeçalho é reconhecido **sem frescura de acento, caixa ou pontuação**:
`Endereço 1 - Número`, `endereco 1 numero` e `ENDEREÇO 1 NUMERO` são a mesma
coluna, e sinônimos comuns (*razão social*, *nome fantasia*, *fone*, *rua*,
*município*) também passam. Dá para importar uma planilha que o escritório já
mantém sem reescrever o cabeçalho. Também lê `.csv`.

**Nada é gravado antes da conferência.** Escolhido o arquivo, a tela lista
linha por linha o que vai acontecer: *Novo cadastro*, *Já cadastrado — fica de
fora*, ou o problema encontrado, em vermelho. Entram nessa conta tipo que não é
PF nem PJ, linha sem nome, texto maior do que o banco aceita, dois endereços do
mesmo tipo com o mesmo nome e nome repetido dentro da própria planilha. As
linhas boas entram; as tortas ficam de fora e a tela diz quantas foram.

**Quem já existe** é reconhecido pelo nome/razão social. Por padrão fica de
fora, para uma reimportação não desfazer o que foi ajustado na tela. Marcando
*Atualizar os clientes que já estão cadastrados*, a ficha é substituída pelo
que vier na planilha — **endereços inclusive**, os que não estiverem lá são
removidos.

### Entrar no sistema

Na primeira execução não existe usuário nenhum, e a tela de entrada pede para
criar o primeiro — é ele que depois cadastra os outros, na aba Cadastros.

A opção **Continuar conectado neste computador** guarda um token na pasta de
dados do usuário — `~/.local/share/rotas/` no Linux,
`%LOCALAPPDATA%\Rotas` no Windows —, com permissão de leitura só para o seu
usuário do sistema operacional. O token vale 30 dias, e o banco guarda apenas o
hash dele: o arquivo sozinho não revela senha nenhuma. Sair pelo botão no canto
da barra de abas apaga o token dos dois lados e volta para a tela de entrada.
Trocar a senha de alguém encerra todos os "continuar conectado" daquela pessoa.

Com o **Caps Lock ligado**, um aviso aparece logo abaixo do campo de senha. O
estado é procurado em três lugares, nesta ordem: o LED do teclado no sysfs
(`/sys/class/leds/*capslock*/brightness`, mantido pelo kernel — funciona no
Wayland, no X11 e no console), o servidor X via XKB, e por último a dedução
pelo que você digita (letra maiúscula sem Shift, ou minúscula com Shift).

Para conferir o que cada caminho responde na sua máquina:

```bash
.venv/bin/python scripts/diagnostico_capslock.py
```

As senhas ficam como hash PBKDF2-SHA256 com 240 mil iterações e sal por usuário
(`app/seguranca.py`) — nenhuma senha é gravada em texto.

### Serviços automáticos

Cliente fixo não precisa ser marcado toda vez. Na ficha do cliente, o cartão
*Serviços automáticos* guarda regras de repetição:

- **Toda semana**, num dia da semana;
- **Dia da semana no mês** — *na primeira segunda-feira*, *na última sexta*;
- **Dia fixo do mês**, com a opção de empurrar para segunda quando cair em fim
  de semana.

A tela mostra as próximas datas enquanto você monta a regra, então dá para
conferir antes de salvar. A agenda abre os serviços dos próximos dois meses
sozinha, toda vez que alguém entra no sistema, e o botão *Gerar agora* faz na
hora.

Três coisas que a geração respeita: nunca cria a mesma data duas vezes, não
mexe no que já está marcado (um serviço cancelado não volta na geração
seguinte), e apagar a regra não apaga os serviços que ela já abriu.

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

- **Cliente e endereço são obrigatórios.** O cliente sai de uma **janela de
  busca** — digitar parte do nome ou do apelido filtra na hora, sem diferença
  de acento ou de maiúsculas ("joao" acha "João") —, e o endereço tem de ser um
  dos daquele cliente. Cliente sem endereço cadastrado não aceita marcação: a
  tela diz isso e manda cadastrar o endereço na aba Clientes. A mesma regra
  vale para os serviços fixos.
- Serviço **Coleta** ou **Retirada**, com data e período (**Manhã**/**Tarde**).
- *Solicitante* é a pessoa do escritório que pediu o serviço.
- Situação: **Pendente**, **Concluído**, **Não realizado** ou **Cancelado**,
  trocada no próprio diálogo. Não realizado e cancelado pedem um **motivo**.
- **Cancelar ≠ Excluir**: mudar a situação para Cancelado mantém o serviço no
  histórico; o botão *Excluir* apaga a linha de vez.
- Excluir um cliente apaga também seus endereços e serviços (a tela avisa
  quantos serão perdidos).
- **Baixa rápida**: cada linha da folha do dia tem um botão redondo na borda
  direita. Um clique marca como concluído; o mesmo botão desfaz.

### Não deu para fazer

Do lado do botão de baixa há o **⤴**, para o serviço que não deu certo no dia:
estabelecimento fechado, ninguém para receber, documentos não prontos. Ele abre
uma tela onde se escolhe (ou escreve) o motivo e, se for o caso, já se remarca
para outro dia num mini calendário.

O que acontece nos bastidores:

- o serviço do dia **não sai do lugar nem é apagado** — fica no histórico como
  *Não realizado*, com o motivo escrito;
- a remarcação é um **serviço novo**, na data nova, que guarda o vínculo com o
  original (coluna `origem_id`). Nos dois dias a agenda mostra a ligação:
  *"Remarcado para 26/09"* e *"Veio do dia 24/09"*;
- um serviço só pode ser remarcado uma vez, e nunca para uma data anterior à
  original;
- desmarcar *Remarcar para outro dia* só registra que não deu, sem abrir nada.

O que não foi remarcado vira **pendência**: no cabeçalho do mês aparece um
botão vermelho com a contagem, que abre a lista dos serviços não realizados sem
remarcação — de lá dá para resolver um por um. Sem pendência, o botão nem
aparece.

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

O botão *Emitir PDF* aparece no cabeçalho do mês e na folha do dia. A escolha do
que sai é feita num mini calendário: no modo **Dia** o clique marca o dia; no
modo **Semana**, a linha inteira acende e sai a semana toda (de domingo a
sábado, igual ao calendário da agenda). Dois formatos:

- **A4 deitado**, em tabela: uma linha por serviço, com colunas de serviço,
  cliente, endereço, quem pediu e situação. A largura da folha horizontal é o
  que permite ver tudo de um serviço sem quebrar linha;
- **Celular**, uma página estreita (95 × 170 mm) em formato de lista, com corpo
  pequeno para caber bastante coisa na tela do telefone.

Os serviços saem **agrupados por cidade e, dentro dela, por bairro** — que é a
ordem em que a rota anda. Cada bloco traz a contagem, e o período (manhã ou
tarde) vira etiqueta em cada serviço.

A folha abre com uma faixa azul: o nome, o período e pastilhas com a contagem
por tipo de serviço. No PDF da semana, cada dia com serviço ganha o número num
selo escuro; os dias vazios viram uma linha discreta, para não comerem meia
página. Cada período tem sua faixa (☀ manhã, ☾ tarde) e cada serviço uma barra
na cor do seu tipo.

Cada serviço sai com quadradinho para marcar, o tipo numa pastilha colorida, a
**razão social ou nome completo** em destaque, o *tratar por* (o apelido, quando é diferente do nome),
o endereço, o telefone, a situação, quem pediu e as **observações** do cliente e
do endereço, quando houver.

O endereço é um **link**: tocando nele no celular, o mapa abre já com o destino
preenchido — é o que leva direto ao GPS.

O PDF é vetorial (fontes embutidas, nada rasterizado), e o desenho é feito numa
grade de 300 dpi: não muda o texto, que é vetor de qualquer jeito, mas deixa as
réguas como fios de 0,085 mm em vez dos traços de 0,34 mm que saíam antes.

## Visual

A identidade vem do logotipo do escritório (`app/recursos/logo.svg`): azul
escuro `#203461`, ciano `#4BBDCD` e laranja `#F9B259`. O logotipo abre a tela
de entrada e cada relatório; o símbolo é o ícone da janela. O fio das três
cores aparece na tela de entrada, no rodapé da janela e, no PDF, só na folha
larga — na estreita do celular ele roubaria espaço. A área de trabalho fica
limpa de marca, para não competir com o conteúdo. Essas cores são a moldura do
sistema; os dados continuam com a própria paleta, que passou pela validação de
daltonismo.

O app tem tema claro próprio e não acompanha o tema escuro do sistema: a
paleta, as fontes e a folha de estilo ficam todas em `app/ui/estilo.py`, e
`aplicar_tema()` é chamado em `main.py` antes de abrir a janela. A direção é
papel de agenda de escritório — fundo branco, pautas finas, azul-caneta como
acento e laranja-carimbo para as retiradas. Texto em **Inter**; **JetBrains
Mono** só nos números e nas etiquetas. Se alguma dessas fontes não estiver
instalada, o Qt cai para a fonte padrão do sistema sem quebrar nada.

## Conexão com o banco pela tela

O botão *Conexão...* na tela de entrada abre a configuração: servidor, porta,
banco, usuário e senha. O botão *Testar conexão* responde com a versão do
PostgreSQL, e só depois de testar é que o *Salvar* grava — num `.env`,
preservando o que não é conexão e deixando o arquivo legível só para você
(permissão 600). Rodando a partir do código, é o `.env` do projeto; instalado,
é o da pasta do usuário (`%APPDATA%\Rotas` ou `~/.config/rotas`).

Se o sistema não conseguir falar com o banco ao abrir, essa mesma tela aparece
com o erro em cima, em vez de o programa simplesmente fechar.

## Migração

Nas primeiras versões o tipo de serviço era um ENUM nativo e o solicitante um
texto solto. Quem já tem banco desse formato roda uma vez:

```bash
.venv/bin/python scripts/migrar_tipos_e_solicitantes.py
```

Ele cria as tabelas novas, transforma os valores antigos em cadastro e troca as
colunas por chaves estrangeiras. Pode rodar de novo sem estragar nada — cada
passo confere antes se já foi feito. Em banco novo, não há o que migrar.

Para o estado *não realizado*, o motivo e o vínculo de remarcação, em bancos
criados antes dessa versão:

```bash
.venv/bin/python scripts/migrar_nao_realizado.py
```

Para os serviços automáticos:

```bash
.venv/bin/python scripts/migrar_servicos_fixos.py
```

Para liberar vários endereços por cliente:

```bash
.venv/bin/python scripts/migrar_varios_enderecos.py
```

As tabelas de usuários, sessões e registro de atividades são criadas sozinhas
por `create_all` na primeira execução — não precisam de script.

## Ícone do programa

O ícone é `app/recursos/icone.svg` — o motoboy da marca. O desenho é deitado e
o espaço que o sistema reserva para um ícone é quadrado, então ele entra
centralizado e esticado até encostar nas laterais, mantendo a proporção: é o
maior tamanho possível sem sair torto.

Depois de mexer no desenho, gere de novo os tamanhos:

```bash
.venv/bin/python scripts/gerar_icones.py
```

Sai `app/recursos/rotas.ico` (é o que o PyInstaller embute no `.exe` e o Inno
Setup usa no instalador), `app/recursos/icones/rotas-<lado>.png`, do 16 ao
512, e `rotas.svg`, o mesmo desenho num quadrado para o tema de ícones do
Linux. Cada tamanho é desenhado a partir do vetor, e não reduzido de um só,
para nenhum sair borrado. Quem desenha é `marca.imagem_icone()` — o mesmo
código que a janela usa, para o atalho e a barra de tarefas não divergirem.

### Atalho no Linux

No Windows quem cria os atalhos é o instalador. No Linux:

```bash
.venv/bin/python scripts/instalar_atalho_linux.py
```

Instala os ícones em `~/.local/share/icons/hicolor` — todos os tamanhos mais o
vetorial em `scalable`, então o ambiente sempre acha uma versão nítida, por
maior que ele queira desenhar — e escreve o `rotas.desktop` no menu e na área
de trabalho. Para desfazer, `--remover`.

## Instalador para Windows

O sistema empacota com PyInstaller e vira instalador com o Inno Setup. **A
montagem precisa acontecer no próprio Windows** — não dá para gerar um `.exe`
a partir do Linux.

No Windows, com Python 3.11+ instalado:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-build.txt
.venv\Scripts\pyinstaller rotas.spec
```

Sai `dist\Rotas\Rotas.exe`, já com o ícone do programa, as fontes embutidas
(Inter e JetBrains Mono não vêm no Windows) e o driver do PostgreSQL. Para
virar instalador, abra `instalador\rotas.iss` no
[Inno Setup](https://jrsoftware.org/isdl.php) e mande compilar: sai
`instalador\saida\rotas-instalador.exe`, que instala para o usuário atual
(sem pedir administrador) e cria os atalhos.

### Banco em outro lugar

O executável é só leitura, então **nada de conexão fica dentro dele**. Na
primeira execução, sem conseguir falar com o banco, o programa abre a tela de
Conexão: informe servidor, porta, banco, usuário e senha, clique em *Testar
conexão* e salve. A configuração vai para a pasta do usuário do Windows
(`%APPDATA%\Rotas\.env`), e o "continuar conectado" para
`%LOCALAPPDATA%\Rotas`. Desinstalar não apaga esses arquivos — reinstalar não
faz perder o apontamento.

No servidor do banco, lembre de liberar o acesso de fora: `listen_addresses`
no `postgresql.conf` e uma linha para a faixa da rede no `pg_hba.conf`.

### Abriu e não apareceu nada

Sem console, um erro antes da primeira janela não tem para onde ir: o processo
sobe e some da vista. Por isso toda falha não tratada é gravada em
`%LOCALAPPDATA%\Rotas\erro.log` (no Linux, `~/.local/share/rotas/erro.log`),
com data, versão, sistema e a conexão que estava valendo. É o primeiro lugar a
olhar.

Se o processo **fica de pé sem abrir janela**, quase sempre é o banco fora de
alcance: um firewall que descarta o pacote em vez de recusar deixa o `connect`
esperando o tempo do sistema operacional, e isso acontece antes de qualquer
tela. A conexão tem um limite de 5 segundos (`ROTAS_DB_TIMEOUT` muda), depois
do qual a tela de Conexão assume. Do computador em questão, dá para conferir o
caminho até o servidor:

```powershell
Test-NetConnection servidor-do-banco -Port 5432
```

## Verificações

```bash
createdb rotas_teste     # uma vez
./testes/rodar.sh
```

O script cria e derruba um banco descartável a cada arquivo, usando a mesma
conexão do `.env` — o banco de trabalho não é tocado. As telas rodam em modo
offscreen, então não abre janela nenhuma.

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
- `eventos.endereco_id` continua aceitando nulo no banco, mesmo com o endereço
  virando obrigatório: o que foi marcado antes da regra segue válido, e apagar
  um endereço do cadastro não pode apagar o histórico de quem já foi atendido
  nele (`ON DELETE SET NULL`). Quem exige é a camada de repositório, e ela
  trata os três casos: serviço novo sempre precisa de endereço; serviço que já
  estava sem endereço continua editável **se** o cliente também não tiver
  nenhum para escolher; e um serviço sem endereço cujo cliente tem endereços
  não é salvo nem remarcado sem que alguém escolha um — a tela avisa e não
  escolhe sozinha, para o serviço não trocar de destino no silêncio.
- Serviço fixo sem endereço fica **parado**: a regra pode ser guardada e
  desligada (senão não haveria como desligar uma que perdeu o endereço), mas a
  geração automática pula as regras sem endereço e anota isso no registro de
  atividades, em vez de abrir serviços sem destino.
