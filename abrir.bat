@echo off
rem Abre o Rotas a partir do codigo, no Windows.
rem
rem Na primeira vez cria o ambiente .venv-win (Python 3.12 + bibliotecas do
rem requirements.txt); das proximas, so abre. A pasta .venv e a do Linux e
rem nao serve aqui.
rem
rem Precisa do uv (https://docs.astral.sh/uv/) ou de um Python 3.12/3.13
rem instalado pelo "py".

setlocal
cd /d "%~dp0"
set "PY=.venv-win\Scripts\python.exe"

if exist "%PY%" goto abrir

echo Preparando o ambiente do Windows (so na primeira vez)...
where uv >nul 2>nul
if %errorlevel%==0 (
    uv venv .venv-win --python 3.12 || goto erro
    uv pip install --python "%PY%" -r requirements.txt || goto erro
) else (
    py -3.12 -m venv .venv-win || goto erro
    "%PY%" -m pip install -r requirements.txt || goto erro
)

:abrir
"%PY%" main.py %*
goto fim

:erro
echo.
echo Nao deu para preparar o ambiente. Instale o uv ou o Python 3.12 e tente de novo.
pause
exit /b 1

:fim
endlocal
