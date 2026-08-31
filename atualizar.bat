@echo off
rem ===========================================================================
rem  Radar Brasil - atualizacao manual do lake, sem depender do GitHub Actions
rem ===========================================================================
rem
rem  Uso:  atualizar.bat            atualiza as fontes diarias
rem        atualizar.bat --tudo     inclui tambem as fontes ANUAIS
rem
rem  A saida aparece na TELA e vai para um ARQUIVO ao mesmo tempo. O caminho do
rem  log e' impresso no fim - e' esse arquivo que voce manda quando algo falhar.
rem
rem  CODIGO DE SAIDA DE CADA ETAPA
rem     0   deu certo
rem    75   falha TRANSITORIA de rede: a fonte nao respondeu agora, o dado
rem         anterior continua valendo, e a atualizacao SEGUE.
rem   outro erro de verdade. So' o TSE e o dbt interrompem tudo.
rem
rem  A distincao entre 75 e o resto esta' em docs/adr/ADR-022. Ela existe porque
rem  tratar tudo como transitorio faria uma fonte que MUDOU DE ENDERECO passar
rem  como aviso, e a serie pararia de atualizar em silencio.
rem ===========================================================================

rem A reentrada existe so' para ter "tee" no Windows: o cmd nao escreve na tela e
rem no arquivo ao mesmo tempo, o PowerShell escreve. A primeira passagem monta o
rem nome do log e re-invoca este mesmo arquivo por dentro do Tee-Object.
if /I "%~1"=="--interno" goto :trabalho

rem O .bat esta' em UTF-8; sem `chcp` o cmd o le' na pagina de codigo antiga e os
rem acentos saem trocados na tela.
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "CARIMBO=%%i"
set "LOG=%~dp0logs\atualizacao_!CARIMBO!.log"

rem Tee em UTF-8, escrevendo na tela e no arquivo linha a linha.
rem
rem NAO e' `Tee-Object`: no PowerShell 5.1, que e' o que vem no Windows, ele grava
rem em UTF-16 e nao aceita `-Encoding`. O log sairia com o dobro do tamanho, com
rem acentos ilegiveis em qualquer editor simples, e o `findstr` da trava de
rem segredo mais abaixo nao acharia NADA dentro dele - conferido em 31/08/2026.
rem
rem `AutoFlush` e' o que faz o arquivo crescer junto com a tela: sem ele, um run
rem interrompido no meio deixaria o log vazio, que e' justamente quando ele mais
rem importa.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$w=New-Object IO.StreamWriter('!LOG!',$false,(New-Object Text.UTF8Encoding($false)));" ^
 "$w.AutoFlush=$true;" ^
 "try{cmd /c \"\"%~f0\" --interno %*\" 2>&1 | ForEach-Object{Write-Host $_;$w.WriteLine($_)}}" ^
 "finally{$w.Close()};" ^
 "exit $LASTEXITCODE"
set "CODIGO=%ERRORLEVEL%"

rem O log foi feito para ser ENVIADO a outra pessoa. Antes de dizer "manda esse
rem arquivo", conferir que nenhum segredo do .env vazou para dentro dele - hoje
rem nenhum comando imprime o salt do CPF nem a senha de FTP, mas um comando novo
rem poderia, e o aviso chegaria tarde demais.
set "VAZOU="
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  set "K=%%a"
  set "V=%%b"
  if /I "!K!"=="RADAR_CPF_SALT"      call :procurar_no_log "!V!" "salt do CPF"
  if /I "!K!"=="RADAR_FTP_PASSWORD"  call :procurar_no_log "!V!" "senha do FTP"
)

echo.
echo ===========================================================================
if defined VAZOU (
  echo   ATENCAO: o log contem !VAZOU! - NAO envie sem apagar essa parte.
  echo.
)
if "!CODIGO!"=="0" (echo   TUDO CERTO.) else (echo   TERMINOU COM FALHA - mande o log abaixo para o Claude:)
echo   !LOG!
echo ===========================================================================
rem A pausa existe para quem abre com dois cliques: sem ela a janela fecha antes
rem de dar tempo de ler. Quem chama de dentro de outro script - o Agendador de
rem Tarefas do Windows, por exemplo - define RADAR_SEM_PAUSA=1 e nao trava.
if not defined RADAR_SEM_PAUSA (
  echo.
  echo Pressione uma tecla para fechar...
  pause >nul
)
exit /b !CODIGO!


rem Procura um segredo dentro do log. `findstr /C:` faz busca literal, sem tratar
rem o texto como expressao regular - importante porque o salt tem `-` e `+`.
:procurar_no_log
if "%~1"=="" exit /b 0
findstr /C:"%~1" "!LOG!" >nul 2>&1 && set "VAZOU=!VAZOU! %~2"
exit /b 0


rem ===========================================================================
:trabalho
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "FALHAS="
set "AVISOS="

rem `delims=` e' obrigatorio: sem ele o `for /f` corta no primeiro espaco e a
rem hora se perde, deixando so' a data.
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"dd/MM/yyyy HH:mm:ss\""') do set "INICIO=%%i"
echo ===========================================================================
echo   RADAR BRASIL - atualizacao do lake
echo   %INICIO%
echo ===========================================================================
echo.

if not exist "%PY%" (
  echo [ERRO] Ambiente virtual nao encontrado em .venv
  echo        Rode antes:  python -m venv .venv
  echo                     .venv\Scripts\pip install -e ".[dbt,dev]"
  exit /b 1
)

rem O .env guarda o projeto do BigQuery e o salt do hash de CPF. Sem ele a carga
rem falharia mais adiante, com um erro bem menos claro que este.
if not exist ".env" (
  echo [ERRO] Arquivo .env nao encontrado.
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  set "CHAVE=%%a"
  rem Um .env salvo como "UTF-8 com BOM" traz tres bytes invisiveis grudados no
  rem nome da PRIMEIRA chave, e a variavel nasceria com nome errado.
  if "!CHAVE:~0,1!"=="﻿" set "CHAVE=!CHAVE:~1!"
  if not "!CHAVE!"=="" if not "!CHAVE:~0,1!"=="#" set "!CHAVE!=%%b"
)
echo   projeto BigQuery: !RADAR_GCP_PROJECT!
echo.

rem === codigo em dia ========================================================
set "CMD=git pull --ff-only"
call :passo "Atualizar o codigo (git pull)" fatal

rem === fontes que mudam todo dia ============================================
rem O TSE e' FATAL de proposito: ele publica apenas o ESTADO ATUAL, sem
rem historico. Um dia sem tirar a foto e' um dia que nao volta.
set "CMD="%PY%" -m ingest.tse load --ano 2026"
call :passo "TSE - candidaturas, bens, vagas, coligacoes" fatal

set "CMD="%PY%" -m ingest.fotos load --ano 2026"
call :passo "Fotos oficiais" tolerante

set "CMD="%PY%" -m ingest.propostas load --ano 2026"
call :passo "Propostas de governo" tolerante

set "CMD="%PY%" -m ingest.planos load"
call :passo "Texto integral dos planos" tolerante

set "CMD="%PY%" -m ingest.legislativo load"
call :passo "Parlamentares em exercicio" tolerante

set "CMD="%PY%" -m ingest.proposicoes load"
call :passo "Atividade legislativa da Camara" tolerante

set "CMD="%PY%" -m ingest.plenario load --ano-inicio 2025 --ano-fim 2026"
call :passo "Votos e presenca em plenario" tolerante

set "CMD="%PY%" -m ingest.chapas load --ano 2026"
call :passo "Chapas - vice e suplentes" tolerante

set "CMD="%PY%" -m ingest.financiamento load --ano 2026"
call :passo "Financiamento de campanha" tolerante

rem === fontes anuais, so' com --tudo =======================================
if /I "%~2"=="--tudo" (
  set "CMD="%PY%" -m ingest.ibge_sidra load --somente-verificados"
  call :passo "IBGE / SIDRA" tolerante
  set "CMD="%PY%" -m ingest.ipeadata load --somente-verificados"
  call :passo "Ipeadata" tolerante
  set "CMD="%PY%" -m ingest.siconfi load"
  call :passo "Tesouro / SICONFI" tolerante
  set "CMD="%PY%" -m ingest.ideb load"
  call :passo "INEP / IDEB" tolerante
  set "CMD="%PY%" -m ingest.rtn load"
  call :passo "Tesouro / RTN" tolerante
) else (
  echo [pulado] Fontes anuais: IBGE, Ipeadata, SICONFI, INEP, RTN
  echo          Sao series ANUAIS - rodar todo dia gasta tempo sem mudar nada.
  echo          Para incluir:  atualizar.bat --tudo
  echo.
)

rem === modelos e testes de dado ============================================
rem FATAL: teste de dado que falha e' sempre erro, nunca instabilidade.
call :passo "dbt build - modelos e testes de dado" dbt

set "CMD="%PY%" scripts\verificar_historico.py"
call :passo "Conferir que o historico continua la" fatal

rem === site ================================================================
set "CMD="%PY%" -m scripts.gerar_site --saida site"
call :passo "Gerar o site" fatal

if defined RADAR_FTP_HOST (
  set "CMD="%PY%" -m scripts.publicar --origem site"
  call :passo "Publicar na Hostinger" tolerante
) else (
  echo [pulado] Publicacao
  echo          As credenciais de FTP nao estao no .env: o LAKE foi atualizado,
  echo          mas o site nao. Para publicar agora, abra
  echo            https://github.com/girocoju/radar-brasil/actions
  echo          rode "pipeline" e marque a caixa "somente_publicar".
  echo.
)

call :resumo
if defined FALHAS exit /b 1
exit /b 0


rem ===========================================================================
rem  :passo  "titulo"  fatal^|dbt^|tolerante        (o comando vem em %CMD%)
rem ===========================================================================
:passo
set "TITULO=%~1"
set "MODO=%~2"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set "T0=%%i"
echo ---------------------------------------------------------------------------
echo [!T0!] !TITULO!
echo ---------------------------------------------------------------------------

if /I "!MODO!"=="dbt" (
  pushd dbt
  set "DBT_PROFILES_DIR=."
  "%PY%" -m dbt.cli.main build
  set "SAIDA=!ERRORLEVEL!"
  popd
) else (
  !CMD!
  set "SAIDA=!ERRORLEVEL!"
)

if "!SAIDA!"=="0" (
  echo    ^> ok
  echo.
  exit /b 0
)

if "!SAIDA!"=="75" (
  rem 75 = EX_TEMPFAIL. Ver ADR-022.
  echo    ^> AVISO: a fonte nao respondeu agora. O dado anterior continua valendo.
  set "AVISOS=!AVISOS!    - !TITULO!#"
  echo.
  exit /b 0
)

echo    ^> FALHA ^(codigo !SAIDA!^) - nao e' instabilidade de rede.
set "FALHAS=!FALHAS!    - !TITULO! ^(codigo !SAIDA!^)#"
if /I "!MODO!"=="tolerante" (
  echo.
  exit /b 0
)
echo.
echo    Esta etapa interrompe a atualizacao: seguir produziria dado incompleto
echo    sem aviso nenhum.
echo.
call :resumo
exit /b 1


rem ===========================================================================
:resumo
echo.
echo ===========================================================================
echo   RESUMO
echo ===========================================================================
if defined AVISOS (
  echo.
  echo   NAO ATUALIZARAM - fonte fora do ar, o dado anterior continua valendo:
  for %%L in ("!AVISOS:#=" "!") do if not "%%~L"=="" echo %%~L
)
if defined FALHAS (
  echo.
  echo   FALHARAM - erro de verdade, precisa de atencao:
  for %%L in ("!FALHAS:#=" "!") do if not "%%~L"=="" echo %%~L
  echo.
  echo   Mande o arquivo de log para o Claude.
)
if not defined AVISOS if not defined FALHAS echo.& echo   Todas as etapas concluidas sem erro.
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"dd/MM/yyyy HH:mm:ss\""') do echo.& echo   fim: %%i
echo ===========================================================================
exit /b 0
