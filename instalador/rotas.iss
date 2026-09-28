; Instalador do Windows para a Agenda do motoboy.
;
; Monte primeiro o programa, no próprio Windows:
;     .venv\Scripts\pyinstaller rotas.spec
; Depois abra este arquivo no Inno Setup (https://jrsoftware.org/isdl.php)
; e mande compilar. Sai `instalador\saida\rotas-instalador-<versao>.exe`.

; A versão tem de bater com app/__init__.py — é de lá que sai a que aparece na
; janela e nas propriedades do Rotas.exe. Ao subir a versão, mude nos dois.
#define Versao "1.0.0"
#define Nome "Agenda do motoboy"
; Como o atalho se chama no menu e na área de trabalho — curto, que é o que
; cabe embaixo de um ícone sem virar reticências.
#define NomeAtalho "MRotas"
#define Empresa "Escritório de Contabilidade"
#define Executavel "Rotas.exe"
#define Origem "..\dist\Rotas"

; Trava boba de esquecimento: sem o build, o Inno reclama aqui em vez de
; gerar um instalador vazio.
#if !FileExists(AddBackslash(SourcePath) + Origem + "\" + Executavel)
  #error Rode "pyinstaller rotas.spec" antes: nao achei dist\Rotas\Rotas.exe
#endif

[Setup]
AppId={{8E2B9A4C-8F2E-4C3B-9E55-6B0A1C9D4E71}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher={#Empresa}
VersionInfoVersion={#Versao}
VersionInfoCompany={#Empresa}
VersionInfoDescription=Instalador da {#Nome}
DefaultDirName={autopf}\Rotas
DefaultGroupName={#NomeAtalho}
DisableProgramGroupPage=yes
OutputDir=saida
; A versão no nome do arquivo: com dois instaladores na mesma pasta, dá para
; saber qual é qual sem abrir nenhum.
OutputBaseFilename=rotas-instalador-{#Versao}
; Dois ícones diferentes, de propósito. Este é o do arquivo do instalador —
; quem clica nele está instalando, não abrindo a agenda.
SetupIconFile=icone.ico
; Já este é o do programa, que é o que aparece em "Aplicativos instalados".
UninstallDisplayIcon={app}\{#Executavel}
UninstallDisplayName={#Nome}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Sem exigir administrador: instala para o usuário atual e evita o UAC.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
; Atualizar por cima com o programa aberto: o Inno pede para fechar em vez de
; falhar copiando um arquivo em uso.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalhodesktop"; Description: "Criar atalho na área de trabalho"; \
    GroupDescription: "Atalhos:"

[Files]
; A pasta inteira que o PyInstaller gerou.
Source: "{#Origem}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Os atalhos levam o nome curto e o ícone do próprio programa.
Name: "{group}\{#NomeAtalho}"; Filename: "{app}\{#Executavel}"; \
    Comment: "{#Nome}"
Name: "{autodesktop}\{#NomeAtalho}"; Filename: "{app}\{#Executavel}"; \
    Comment: "{#Nome}"; Tasks: atalhodesktop

[Run]
Filename: "{app}\{#Executavel}"; Description: "Abrir agora"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; A configuração de conexão e a sessão salva ficam no perfil do usuário e não
; são apagadas: quem desinstalar e instalar de novo não perde o que apontou.
Type: dirifempty; Name: "{app}"
