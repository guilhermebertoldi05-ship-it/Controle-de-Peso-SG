@echo off
echo =========================================
echo   Iniciando o Sistema de Controle de Peso...
echo =========================================
echo.

echo [1/2] Rodando o Robo Extrator de Peso...
python peso.py

echo.
echo [2/2] Rodando o Refinador de Dados...
python refinador_peso.py

echo.
echo =========================================
echo   Processo 100%% Concluido!
echo =========================================
