# Rotas — arquivos da marca

## Cores
| Nome | Hex | Uso |
|---|---|---|
| Marinho Métodos | `#203461` | base, textos, fundo do ícone |
| Ciano Rota | `#4BBDCD` | o traço; destaques e seleção (nunca texto sobre branco) |
| Âmbar Destino | `#F9B259` | pino, botão principal, status pendente |
| Tinta | `#16244A` | títulos fortes, texto sobre âmbar |
| Ardósia | `#5B6782` | texto secundário |
| Névoa | `#F4F6FA` | fundo da janela |
| Linha | `#E1E6F0` | bordas |

Faixa tricolor: âmbar 25% · ciano 33% · marinho 42%.

## Fontes (pasta `fontes/`, licença SIL OFL)
- Sora Bold/ExtraBold — logo, títulos, números grandes
- Plus Jakarta Sans — interface
- JetBrains Mono — datas, horários, CNPJ

## Onde usar no programa
- `icone/rotas.ico` — ícone da janela, do executável (PyInstaller `icon=`) e do instalador (Inno Setup `SetupIconFile`)
- `icone/rotas-*.png` — mesmos desenhos em tamanhos fixos (16 a 512)
- `logo/rotas-logo-escuro*.svg` — cabeçalho escuro e tela de entrada
- `logo/rotas-logo-claro*.svg` — PDF e fundos claros
- `simbolo/` — símbolo sozinho (claro, escuro, mono)
