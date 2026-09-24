; Instalador do Windows para a Agenda do motoboy.
;
; Monte primeiro o programa:
;     pyinstaller rotas.spec
; Depois abra este arquivo no Inno Setup (https://jrsoftware.org/isdl.php)
; e mande compilar. Sai `instalador\saida\rotas-instalador.exe`.

#define Nome "Agenda do motoboy"
#define Versao "1.0.0"
#define Empresa "Escritório de Contabilidade"
#define Executavel "Rotas.exe"

[Setup]
AppId={{8E2B9A4C-8F2E-4C3B-9E55-6B0A1C9D4E71}
AppName={#Nome}
AppVersion={#Versao}
AppPublisher={#Empresa}
DefaultDirName={autopf}\Rotas
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
OutputDir=saida
OutputBaseFilename=rotas-instalador
SetupIconFile=..\app\recursos\rotas.ico
UninstallDisplayIcon={app}\{#Executavel}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Sem exigir administrador: instala para o usuário atual e evita o UAC.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalhodesktop"; Description: "Criar atalho na área de trabalho"; \
    GroupDescription: "Atalhos:"

[Files]
; A pasta inteira que o PyInstaller gerou.
Source: "..\dist\Rotas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Executavel}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; Tasks: atalhodesktop

[Run]
Filename: "{app}\{#Executavel}"; Description: "Abrir agora"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; A configuração de conexão e a sessão salva ficam no perfil do usuário e não
; são apagadas: quem desinstalar e instalar de novo não perde o que apontou.
Type: dirifempty; Name: "{app}"
