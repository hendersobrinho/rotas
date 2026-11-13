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

No Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

No Windows, dê dois cliques no `abrir.bat` (ou rode no terminal). Na primeira
vez ele cria o ambiente `.venv-win` com o `uv` (ou com o `py -3.12`, se não
houver `uv`) e instala as bibliotecas; das próximas, só abre o programa. Na
mão seria:

```powershell
uv venv .venv-win --python 3.12
uv pip install --python .venv-win\Scripts\python.exe -r requirements.txt
.venv-win\Scripts\python main.py
```

A pasta `.venv` é do Linux e não serve no Windows; por isso o nome separado.

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

Na primeira vez que o programa abre num computador, acontece nesta ordem:

1. **se ninguém apontou um banco ainda**, a tela de Conexão abre logo de cara,
   antes de qualquer tentativa — não faria sentido tentar o `postgres@localhost`
   do padrão, que ou recusa, ou fica esperando. Informe o servidor, teste e
   salve; fica guardado e das próximas vezes o programa abre direto;
2. conecta no banco e **cria as tabelas** que faltam (`create_all`);
3. como ainda não existe usuário **do sistema**, a tela de entrada pede para
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
│   ├── socios.py          vínculos de sócios entre clientes
│   ├── solicitantes.py    cadastro de quem pede
│   ├── usuarios.py        contas, autenticação e sessões salvas
│   └── logs.py            gravação e consulta do registro de atividades
└── ui/
    ├── marca.py           cores da marca, logotipo e ícone do programa
    ├── estilo.py          tema claro: paleta, fontes e folha de estilo
    ├── main_window.py     janela e a barra lateral (Cadastro de clientes, Agenda, Lembrancinhas…)
    ├── eventos_tab.py     calendário do mês e a folha do dia
    ├── calendario.py      a grade do mês
    ├── evento_dialog.py   diálogo de inclusão e edição de um serviço
    ├── clientes_tab.py    lista, ficha (só leitura), cadastro e sócios
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
    ├── relatorio_pdf.py   PDF da rota: cabeçalho, rodapé e atrasados
    ├── datas.py           datas em português, agrupamento e intervalos
    ├── widgets.py         etiquetas, botões segmentados, tabelas e endereço
    └── mensagens.py       caixas de erro e confirmação
testes/
├── comum.py               banco descartável e dados de exemplo
├── teste_interface.py     entrada, conexão, clientes, agenda, cadastros e painel
├── teste_recorrencia.py   regras de repetição e abertura automática
├── teste_enderecos.py     endereços, contatos (quem recebe) e lembrancinhas
├── teste_obrigatorios.py  cliente e endereço obrigatórios
├── teste_importacao.py    modelo da planilha, leitura, conferência e gravação
├── teste_conexao.py       primeiro acesso, tela de Conexão e limite de espera
├── teste_pdf.py           logotipo, cores, folha deitada e versão celular
├── rodar.py               roda tudo num banco de teste (Windows e Linux)
└── rodar.sh               o mesmo, em bash
scripts/
├── migrar_tipos_e_solicitantes.py   migração para o formato com cadastros
├── migrar_nao_realizado.py          migração do estado "não realizado"
├── migrar_servicos_fixos.py         migração dos serviços automáticos
├── migrar_varios_enderecos.py       libera vários endereços por cliente
├── gerar_icones.py                  ícone do programa em todos os tamanhos
├── exemplos.py                      cadastra (e --apagar remove) dados de exemplo
├── instalar_atalho_linux.py         atalho no menu e na área de trabalho
└── diagnostico_capslock.py          o que cada leitura do Caps Lock responde
```

A regra é: `ui/` nunca fala com o banco direto — sempre passa pelo
`repository/`, que por sua vez só conhece `models` e `schemas`.

## Como o sistema funciona

### Clientes

A tela de clientes é feita em três passos, um de cada vez:

1. **Lista** — todos os clientes, com busca (nome, apelido, telefone, cidade
   ou bairro, sem ligar para acento) e o filtro *Todos · Empresas · Pessoas*.
   A coluna *Vínculos* mostra quantos sócios a empresa tem, ou de quantas
   empresas a pessoa faz parte. Clicar no cliente abre a ficha.
2. **Ficha** — o cliente como ele é, **só para ler**: contato e observação,
   os endereços, os sócios (ou as empresas), os serviços automáticos e o
   histórico. Nada se edita por engano aqui.
3. **Cadastro** — o formulário, aberto pelo *Novo cliente* da lista ou pelo
   *Editar cadastro* da ficha. *Salvar cliente* grava e volta para a ficha;
   *Cancelar* volta sem mexer em nada.

Regras do cadastro:

- Tipo **PF** ou **PJ**; o campo *Nome* guarda o nome completo ou a razão social.
- O *apelido / fantasia* é o que aparece nas listas e nos combos.
- **Quem recebe e telefone**: cada linha é uma pessoa do cliente (Ana, a
  recepção, o financeiro) com o telefone dela; *Adicionar outra pessoa /
  telefone* acrescenta mais, e o ✕ tira. O primeiro telefone é o principal —
  o que aparece na lista e entra na busca (que também acha pelo nome de quem
  recebe). Na hora de marcar um serviço (e nos serviços automáticos), o campo
  **Aos cuidados de** escolhe a pessoa; ele aparece na agenda, nos cartões de
  *Rota e baixas* e no PDF como *A/C ANA · (31) …*, sempre abaixo do nome do
  cliente. A remarcação leva a mesma pessoa. Nos bancos de antes, o telefone
  de cada cliente vira o primeiro contato, sem nome, na primeira abertura.
- Cada cliente tem **quantos endereços precisar**. *Adicionar endereço*
  acrescenta um bloco; o *Remover* de cada um tira. Cada endereço tem um tipo
  (residencial ou comercial) e um **nome** — *Matriz*, *Filial Barreiro*,
  *Depósito* —, que é como ele aparece na hora de marcar um serviço e nos
  relatórios — sempre com o tipo à vista: *🏢 MATRIZ (Comercial)*,
  *🏠 CASA (Residencial)*. Dois endereços do mesmo tipo com o mesmo nome não
  passam.
- Um bloco deixado inteiramente em branco é ignorado, e um endereço removido da
  tela sai do banco quando você salva.
- O **histórico** são os serviços do cliente, do mais recente para o mais
  antigo, agrupados por **semana**, **mês** ou **ano**. Dois cliques numa linha
  abrem aquele dia na agenda.

#### Sócios

Uma empresa (PJ) pode ter **pessoas ligadas a ela** — sócio,
sócio-administrador, procurador, responsável (o papel é texto livre, com
sugestões). A pessoa precisa estar cadastrada como cliente, normalmente PF.

- Na ficha da **empresa**, o cartão *Sócios e responsáveis* lista cada pessoa
  com o papel, o telefone e os endereços — para quando a entrega é na casa de
  um sócio. *Vincular sócio* escolhe a pessoa.
- Na ficha da **pessoa**, o cartão *Empresas* mostra de quais empresas ela faz
  parte; *Vincular a empresa* faz o caminho inverso.
- Cada vínculo tem *Abrir ficha*, *Editar cadastro*, *Papel* e *Desvincular*.
  *Editar cadastro* abre o cadastro do sócio (ou da empresa) ali mesmo e, ao
  salvar ou cancelar, volta para a ficha de onde se partiu; *Abrir ficha*
  mostra o botão *Voltar para …* no topo. Desfazer o vínculo
  não mexe nos dois cadastros; excluir um cliente desfaz os vínculos dele.
- Uma PJ também pode ser sócia de outra (holding): aparece no cartão *Faz
  parte de* da ficha dela.

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
criar o primeiro — é ele que depois cadastra os outros, na aba Configurações.

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

### Configurações

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

### Rota e baixas

A tela **Rota e baixas** é onde a rota sai e onde se acompanha o que ainda
espera confirmação. No topo, o botão **Emitir rota** e os **filtros**: cliente
ou endereço, tipo de serviço e período (dia todo, manhã, tarde). Os filtros só
escondem cartões — o contador da barra lateral continua contando tudo.

O quadro tem quatro colunas:

- **Atrasados** — dias que já passaram com o serviço ainda pendente: ninguém
  confirmou se o motoboy foi. Mais antigos em cima, com "há N dias";
- **Hoje** — o que está na rua, para ir dando baixa ao longo do dia;
- **Não realizados** — não deu para fazer e ainda não foi remarcado;
- **Baixados** — concluídos nos últimos sete dias, para conferir e desfazer
  algum engano.

O cartão muda de coluna **arrastando** ou pelos botões dele (*Dar baixa*, *Não
deu*, *Remarcar*, *Desfazer*); dois cliques abrem o serviço. Os atrasados têm
*Baixar todos* (os que estão à vista, com o filtro), com confirmação. O item da
barra lateral mostra quantos pedem ação (atrasados + não realizados), e o botão
*Sem baixa* da agenda leva para cá.

**Emitir rota com os atrasados**: quando há serviços de dias anteriores sem
baixa, a janela de *Emitir rota* mostra quantos são e oferece **Incluir os
atrasados na rota** (marcado por padrão). Marcado, o PDF ganha uma seção
*Pendentes de dias anteriores* antes do dia, com a data de origem de cada
serviço — assim o motoboy leva junto o que ficou para trás.

No **calendário**, só o que está em aberto fica com a cor do tipo de serviço:
o que já teve baixa fica **verde com ✓**, o não realizado vermelho com ✕ e o
cancelado cinza riscado. Os em aberto aparecem primeiro na célula. No canto do
dia, um selo âmbar com a contagem marca dia que passou com algo sem baixa; um
✓ verde, dia com tudo baixado.

### Lembrancinhas

Cadastro à parte para quem recebe a **lembrancinha de fim de ano** do
escritório: nome, a quem entregar, telefone, o presente, endereço e observação
(em maiúsculas, como os clientes). *Trazer de Clientes* começa a ficha a partir
de um cliente da agenda, já com o endereço comercial, e deixa os dois ligados.

Cada **campanha** (ano) tem a sua situação por destinatário: *A entregar*,
*Entregue* (com a data) ou *Não enviar*. Quando o ano vira, todo mundo volta a
*A entregar* e o histórico dos anos anteriores continua anotado — as setas ao
lado do ano navegam entre campanhas. Em janeiro a tela ainda abre na campanha
do ano que acabou. Quem não deve mais receber é desmarcado em *Recebe
lembrancinha* e sai da contagem sem perder o histórico.

**Pelo cadastro do cliente**: cada endereço do cadastro (de empresa ou de
sócio) tem a opção **🎁 Endereço das lembrancinhas**. Marcando e salvando, o
cliente entra sozinho nesta lista com aquele endereço — sem cadastrar de novo.
Só um endereço por cliente pode ser o das lembrancinhas (marcar um desmarca o
outro); mudar o endereço no cadastro atualiza a lista, e desmarcar tira o
cliente da lista, guardando o histórico das entregas. Quem recebe lembrancinha
aparece com 🎁 na lista de clientes, com o selo *Lembrancinha 2026 · situação*
na ficha e *Lembrancinhas* no endereço escolhido.

A barra de andamento mostra quantos já foram entregues; *Exportar planilha*
gera um .xlsx (ou .csv) com a lista filtrada, para imprimir ou mandar para quem
vai entregar.

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

### PDF da rota

*Emitir rota* fica na tela **Rota e baixas** e também na agenda (no mês e na
folha do dia). A escolha do que sai é feita num mini calendário: no modo
**Dia** o clique marca o dia; no modo **Semana**, sai a semana toda (de
domingo a sábado). Dois formatos:

- **A4 deitado**, em tabela: uma linha por serviço, com colunas de período,
  serviço, cliente, endereço, quem pediu e situação;
- **Celular**, uma página estreita (95 × 170 mm) em formato de lista, com corpo
  pequeno para caber bastante coisa na tela do telefone.

**Toda página** tem cabeçalho e rodapé:

- **cabeçalho** — o logotipo, *Rota do motoboy* com o período por extenso, a
  hora da emissão e o total de serviços (na folha larga), fechado pela faixa
  tricolor da marca de ponta a ponta;
- **rodapé** — o símbolo da marca, *emitido em … por …* e a numeração
  *página 1 / 3* numa pastilha marinho.

A primeira página abre com o título e os **números da rota**: total, manhã,
tarde e, se foram incluídos, os atrasados — e pastilhas com a contagem por tipo
de serviço. Depois vêm os atrasados (se incluídos) e os serviços do dia,
**agrupados por cidade e, dentro dela, por bairro** — a ordem em que a rota
anda. No PDF da semana, cada dia ganha o número num selo marinho; os dias
vazios viram uma linha discreta.

Cada serviço sai com quadradinho para marcar, o tipo numa pastilha colorida, o
período, a **razão social ou nome completo** em destaque, o *tratar por*, o
endereço, o telefone, a situação, quem pediu e as **observações** do cliente e
do endereço. O endereço é um **link**: tocando nele no celular, o mapa abre já
com o destino.

O PDF sai sempre nas **cores do tema claro**, mesmo com o programa no escuro —
ele vai para o papel. É vetorial (fontes embutidas), desenhado numa grade de
300 dpi, com fios finos de verdade.

## Visual

A identidade é a da pasta da marca (`rotas-marca/`, com o guia em
`LEIA-ME.md`); os arquivos que o programa usa ficam em `app/recursos/marca/`,
`app/recursos/fontes/` e `app/recursos/icones/`.

- **Cores**: Marinho `#203461` (base, barra lateral, fundo do ícone), Ciano
  `#4BBDCD` (foco e seleção — nunca texto em fundo branco), Âmbar `#F9B259`
  (botão principal, com texto em Tinta, e tudo que está pendente), Tinta
  `#16244A`, Ardósia `#5B6782`, Névoa `#F4F6FA` (fundo) e Linha `#E1E6F0`.
- **Faixa tricolor**: âmbar 25% · ciano 33% · marinho 42%, no alto da área de
  trabalho, no rodapé da tela de entrada e no PDF largo.
- **Fontes**: **Sora** nos títulos e números grandes, **Plus Jakarta Sans** na
  interface, **JetBrains Mono** em datas e etiquetas — todas embarcadas (licença
  SIL OFL), porque no Windows elas não vêm instaladas.

A janela tem uma **barra lateral marinho** com o logotipo, a navegação (com
ícones desenhados em `app/ui/icones.py`), o contador de baixas, o botão de
atualização quando houver e o cartão de quem está conectado. Ao abrir, uma
**tela de abertura** com a marca e a faixa animada cobre a conexão com o banco;
a **tela de entrada** tem o painel marinho da marca ao lado do formulário.

Os dados continuam com a própria paleta (os quatro tons dos tipos de serviço),
que passou pela validação de daltonismo.

### Tela de espera

Quando abrir uma tela demora (muitos clientes, banco em outro computador), a
janela fica **desfocada** por baixo e, no meio, o **R da marca se desenha**:
o traço ciano percorre a letra como uma rota e o pino âmbar cai no fim, com a
faixa tricolor correndo embaixo. O trabalho de banco roda em segundo plano, por
isso a animação não trava; cliques e teclas esperam até terminar. Se carregar
em menos de 0,15 s, nada aparece — e, aparecendo, fica ao menos meio segundo,
para não piscar. Está em `app/ui/carregando.py` (`esperar(tela, função,
texto)`), e hoje é usada na lista e na ficha de clientes.

As listas longas (clientes, lembrancinhas, registro, histórico, busca de
cliente) são preenchidas **em lote**: as colunas só são medidas no fim. Antes,
cada célula escrita fazia o Qt medir a coluna inteira de novo — com 1.500
clientes a lista levava minutos; agora, menos de meio segundo.

### Tema escuro

O botão de **lua** no pé da barra lateral troca para o tema escuro (e o de
**sol** volta para o claro). A escolha fica guardada no computador, por
usuário do Windows; a janela é remontada na mesma tela, sem pedir login.

O escuro foi feito para **não cansar a vista**: fundo azul-noite em vez de
preto, texto gelo em vez de branco puro, e contraste medido — texto principal
perto de 13:1, o mais apagado acima de 5:1. As cores dos tipos de serviço e
das situações têm versões próprias para o fundo escuro, e o âmbar continua
sendo o botão principal. A tela de abertura, o painel da entrada e o PDF ficam
nas cores da marca nos dois temas.

As duas paletas (`CORES_CLARAS` e `CORES_ESCURAS`) ficam em
`app/ui/estilo.py`. `ROTAS_TEMA=claro` (ou `escuro`) força um tema e não
grava a escolha — é o que os testes usam.

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

## Dados de exemplo

Para ver o programa com movimento — atrasados, serviços de hoje, baixados, não
realizados, remarcados, cancelados, serviços automáticos, sócios e
lembrancinhas:

```bash
.venv-win\Scripts\python scripts\exemplos.py           # cadastra
.venv-win\Scripts\python scripts\exemplos.py --apagar  # remove tudo de novo
```

O que foi criado fica anotado em `exemplos.json`, na pasta de dados do
programa; o `--apagar` remove exatamente isso e não toca no resto.

## Ícone do programa

O ícone é `app/recursos/icone.svg` — o R com o pino, no quadrado marinho da
marca (`rotas-marca/icone/`). O `.ico` e os PNGs vêm prontos da pasta da marca;
o instalador usa o mesmo `.ico`.

Depois de mexer no desenho, gere de novo os tamanhos:

```bash
.venv/bin/python scripts/gerar_icones.py
```

Sai `app/recursos/rotas.ico` (é o que o PyInstaller embute no `.exe`), `app/recursos/icones/rotas-<lado>.png`, do 16 ao
512, e `rotas.svg`, o mesmo desenho num quadrado para o tema de ícones do
Linux. Cada tamanho é desenhado a partir do vetor, e não reduzido de um só,
para nenhum sair borrado. Quem desenha é `marca.imagem_icone()` — o mesmo
código que a janela usa, para o atalho e a barra de tarefas não divergirem.

O mesmo comando gera `instalador/icone.ico`, o ícone do arquivo do instalador,
a partir de `instalador/icone.png`. Esse vem de um PNG de 96 px, então o .ico
para nos 96: ampliar só acrescentaria borrão, e o Windows amplia igual sozinho
quando precisa de um tamanho maior. Ele fica em `instalador/` de propósito —
não é recurso de execução e não tem por que viajar dentro do `.exe`.

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
(Sora, Plus Jakarta Sans e JetBrains Mono não vêm no Windows) e o driver do
PostgreSQL. Para virar instalador, abra `instalador\rotas.iss` no
[Inno Setup](https://jrsoftware.org/isdl.php) e mande compilar: sai
`instalador\saida\rotas-instalador-1.5.0.exe` — a versão vai no nome do
arquivo —, que instala para o usuário atual (sem pedir administrador) e cria
os atalhos. O atalho, no menu e na área de trabalho, chama-se **MRotas**; o
nome por extenso fica na dica que aparece ao passar o mouse.

### Atualização automática

O programa instalado consulta o GitHub (`hendersobrinho/rotas`) alguns
segundos depois de abrir. Havendo versão nova, aparece na barra lateral o botão
âmbar **Atualizar para X.Y.Z**: o clique mostra as notas da versão e, com
*Atualizar agora*, baixa o instalador, confere o arquivo (tamanho e sha256 que
o GitHub publica) e o executa em modo silencioso — o programa fecha, os
arquivos são trocados e ele abre de novo sozinho. O banco não é tocado. O link
*buscar atualização*, embaixo na barra lateral, faz a consulta na hora.

Para publicar uma versão:

1. Suba a versão em `app/__init__.py` **e** em `instalador/rotas.iss`;
2. gere o `.exe` e o instalador como acima;
3. crie a release no GitHub com a tag `v1.5.0` (o número da versão), escreva as
   novidades no texto — é o que aparece para quem vai atualizar — e anexe o
   `rotas-instalador-1.5.0.exe`. Rascunho e pré-lançamento são ignorados.

A consulta usa a API pública do GitHub, então **o repositório precisa ser
público** (ou as releases não aparecem). Rodando a partir do código a consulta
automática fica desligada, e `ROTAS_SEM_ATUALIZACAO=1` desliga também no
programa instalado.

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

```powershell
.venv-win\Scripts\python testes\rodar.py              # Windows
.venv/bin/python testes/rodar.py                      # Linux (ou ./testes/rodar.sh)
.venv-win\Scripts\python testes\rodar.py pdf          # só os que têm "pdf" no nome
```

O usuário do `.env` precisa ter permissão de criar banco (`CREATEDB`). Para
usar outro servidor só nos testes, defina `ROTAS_URL_TESTE`.

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
