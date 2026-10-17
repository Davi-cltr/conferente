@echo off
chcp 65001 >nul
title Conferente
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  O Python nao foi encontrado neste computador.
  echo  Instale em https://www.python.org/downloads/ e marque a opcao
  echo  "Add python.exe to PATH" na primeira tela do instalador.
  echo  Depois, abra este arquivo de novo.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Primeira execucao: preparando o ambiente ^(1 a 2 minutos^)...
  python -m venv .venv || goto erro
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
)

rem Reinstala quando o pyproject.toml muda (nova versao do Conferente)
fc /b pyproject.toml ".venv\pyproject.instalado" >nul 2>nul
if errorlevel 1 (
  echo  Atualizando o Conferente...
  ".venv\Scripts\python.exe" -m pip install --quiet -e . || goto erro
  copy /y pyproject.toml ".venv\pyproject.instalado" >nul
)

echo.
echo  Conferente rodando em http://127.0.0.1:8000
echo  Abra "Comecar teste gratis" para criar uma conta. Notas de exemplo: pasta tests\amostras.
echo  Para encerrar, feche esta janela.
echo.
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn conferente.web.app:app --host 127.0.0.1 --port 8000
goto fim

:erro
echo.
echo  Algo deu errado na instalacao. Tire um print desta janela e mande para o Claude.
pause
exit /b 1

:fim
