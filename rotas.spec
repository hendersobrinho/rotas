# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para empacotar a Agenda do motoboy.

    pyinstaller rotas.spec

Gera `dist/Rotas/Rotas.exe` (no Windows) ou `dist/Rotas/Rotas` (no Linux).
O instalador do Windows é montado em cima dessa pasta — ver instalador/.

Vale lembrar: o executável é só leitura. A conexão com o banco e o "continuar
conectado" ficam na pasta do usuário do sistema (ver app/caminhos.py), e é a
tela de Conexão que grava lá — nada de .env dentro do pacote.
"""

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

NOME = "Rotas"

# Os arquivos que o programa lê em tempo de execução: logotipo, ícone e as
# fontes, que no Windows não estão instaladas.
dados = [("app/recursos", "app/recursos")]

# O driver do PostgreSQL carrega binários próprios.
binarios = collect_dynamic_libs("psycopg_binary")
ocultos = collect_submodules("psycopg") + [
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
