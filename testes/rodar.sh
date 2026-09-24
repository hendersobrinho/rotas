#!/usr/bin/env bash
# Roda as verificações num banco descartável.
#
#   ./testes/rodar.sh
#
# Usa o usuário do .env; para outro banco, exporte ROTAS_URL_TESTE.
set -u
cd "$(dirname "$0")/.."

BANCO="${ROTAS_BANCO_TESTE:-rotas_teste}"
dropdb --if-exists "$BANCO" >/dev/null 2>&1
createdb "$BANCO" || { echo "não deu para criar o banco $BANCO"; exit 1; }
rm -rf testes/.dados testes/.saida

falhas=0
for arquivo in testes/teste_*.py; do
    nome=$(basename "$arquivo" .py)
    saida=$(PYTHONPATH=testes .venv/bin/python "$arquivo" 2>&1 \
            | grep -v "Gtk-WARNING\|Theme parsing\|propagateSizeHints")
    if echo "$saida" | grep -q " OK$"; then
        echo "OK      $nome"
    else
        echo "FALHOU  $nome"
        echo "$saida" | tail -12
        falhas=1
    fi
    dropdb --if-exists "$BANCO" >/dev/null 2>&1
    createdb "$BANCO" >/dev/null 2>&1
    rm -rf testes/.dados
done

dropdb --if-exists "$BANCO" >/dev/null 2>&1
rm -rf testes/.dados
[ $falhas -eq 0 ] && echo "--- tudo passou"
exit $falhas
