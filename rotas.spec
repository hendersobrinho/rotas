# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para empacotar a Agenda do motoboy.

    pyinstaller rotas.spec

Gera `dist/Rotas/Rotas.exe` (no Windows) ou `dist/Rotas/Rotas` (no Linux).
O instalador do Windows é montado em cima dessa pasta — ver instalador/.

Vale lembrar: o executável é só leitura. A conexão com o banco e o "continuar
conectado" ficam na pasta do usuário do sistema (ver app/caminhos.py), e é a
tela de Conexão que grava lá — nada de .env dentro do pacote.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

sys.path.insert(0, SPECPATH)
from app import __version__ as VERSAO   # noqa: E402 - app/__init__ só tem isto

NOME = "Rotas"
DESCRICAO = "Agenda do motoboy"
EMPRESA = "Escritório de Contabilidade"


def recurso_de_versao() -> str | None:
    """Grava o recurso que vira as propriedades do .exe no Windows.

    É texto puro, montado a partir de `app.__version__`, para a versão do
    executável, a do instalador e a que a janela mostra virem todas do mesmo
    lugar. Fora do Windows não existe esse recurso — e o módulo do PyInstaller
    que o grava depende do `pefile`, que só é instalado lá.
    """
    if not sys.platform.startswith("win"):
        return None

    partes = [int(pedaco) for pedaco in VERSAO.split(".")]
    partes += [0] * (4 - len(partes))
    quadra = ", ".join(str(pedaco) for pedaco in partes)

    # 0416 = português do Brasil; 04B0 = página de código Unicode (1200).
    texto = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quadra}), prodvers=({quadra}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', '{EMPRESA}'),
      StringStruct('FileDescription', '{DESCRICAO}'),
      StringStruct('FileVersion', '{VERSAO}'),
      StringStruct('InternalName', '{NOME}'),
      StringStruct('LegalCopyright', '{EMPRESA}'),
      StringStruct('OriginalFilename', '{NOME}.exe'),
      StringStruct('ProductName', '{DESCRICAO}'),
      StringStruct('ProductVersion', '{VERSAO}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])]),
  ]
)
"""
    pasta = os.path.join(SPECPATH, "build")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, "versao_windows.txt")
    with open(destino, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return destino


# Os arquivos que o programa lê em tempo de execução: logotipo, ícone e as
# fontes, que no Windows não estão instaladas.
dados = [("app/recursos", "app/recursos")]

# O driver do PostgreSQL carrega binários próprios.
binarios = collect_dynamic_libs("psycopg_binary")
# O openpyxl entra inteiro: é ele que lê e escreve a planilha de clientes, e
# parte dos módulos dele só é importada na hora de gravar o arquivo.
ocultos = collect_submodules("psycopg") + collect_submodules("openpyxl") + [
    "psycopg_binary",
    "psycopg.pq",
    "app.repository",
    "app.ui",
]

analise = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binarios,
    datas=dados,
    hiddenimports=ocultos,
    hookspath=[],
    runtime_hooks=[],
    # Nada de Qt que não se usa, para o pacote não inchar.
    excludes=[
        "PySide6.Qt3DCore",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "tkinter",
        "matplotlib",
        "numpy",
        "PIL",
    ],
    noarchive=False,
)

pyz = PYZ(analise.pure)

exe = EXE(
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name=NOME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # é um programa de janela: sem console atrás
    disable_windowed_traceback=False,
    icon="app/recursos/rotas.ico",
    version=recurso_de_versao(),
)

collect = COLLECT(
    exe,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NOME,
)
