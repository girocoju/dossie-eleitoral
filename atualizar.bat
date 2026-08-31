@echo off
rem ===========================================================================
rem  Radar Brasil - atualizacao manual do lake, sem depender do GitHub Actions
rem ===========================================================================
rem
rem  Uso:  atualizar.bat            fontes diarias
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
rem  A distincao esta' em docs/adr/ADR-022. Ela existe porque tratar tudo como
rem  transitorio faria uma fonte que MUDOU DE ENDERECO passar como aviso, e a
rem  serie pararia de atualizar em silencio.
rem
rem  TUDO EM ASCII, de proposito: texto acentuado em .bat depende da pagina de
rem  codigo do console e sai trocado na primeira situacao que nao for a ideal.
rem ===========================================================================

if /I "%~1"=="--interno" goto :trabalho

chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "CARIMBO=%%i"
set "LOG=%~dp0logs\atualizacao_!CARIMBO!.log"
set "CODIGO=1"

rem CAMINHO CURTO, e nao `%~f0`.
rem
rem Este projeto vive em "...\OneDrive\Area de Trabalho\...", com ESPACOS.
rem Passar isso por dentro de cmd -^> powershell -^> cmd quebra: o cmd parte no
rem primeiro espaco e tenta executar "C:\Users\giroc\OneDrive\Area". Foi
rem exatamente o que aconteceu na primeira execucao de verdade, em 31/08/2026 -
rem e NAO apareceu no teste, porque a pasta de teste nao tinha espaco no nome.
rem
rem `%~s0` devolve o nome curto 8.3, sem espaco e sem acento: o problema
rem desaparece na origem, em vez de exigir mais uma camada de aspas.
set "SELF=%~s0"
echo !SELF!| findstr /C:" " >nul && (
  echo [ERRO] O caminho curto ainda contem espaco:
  echo        !SELF!
  echo        Os nomes 8.3 devem estar desligados neste volume. Mova o projeto
  echo        para uma pasta sem espacos, por exemplo C:\radar-brasil
  goto :fim_externo
)

rem Log, argumentos e marca de resultado viajam por VARIAVEL DE AMBIENTE: dentro
rem do PowerShell viram `$env:LOG` e `$env:ARGS`, que nao passam por camada de
rem aspas nenhuma, e ai' espaco e acento no caminho sao irrelevantes.
set "ARGS=%*"
set "MARCA=%TEMP%\radar_codigo_%RANDOM%.txt"
if exist "!MARCA!" del "!MARCA!" >nul 2>&1

rem Tee em UTF-8, escrevendo na tela e no arquivo linha a linha.
rem
rem NAO e' `Tee-Object`: no PowerShell 5.1, que e' o que vem no Windows, ele
rem grava em UTF-16 e nao aceita `-Encoding`. O log sairia com o dobro do
rem tamanho, ilegivel em editor simples, e o `findstr` da trava de segredo mais
rem abaixo nao acharia NADA dentro dele - conferido em 31/08/2026.
rem
rem `AutoFlush` e' o que faz o arquivo crescer junto com a tela: sem ele, um run
rem interrompido no meio deixaria o log vazio, que e' justamente quando ele mais
rem importa.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$w=New-Object IO.StreamWriter($env:LOG,$false,(New-Object Text.UTF8Encoding($false)));" ^
 "$w.AutoFlush=$true;" ^
 "try{cmd /c \"$env:SELF --interno $env:ARGS\" 2>&1 | ForEach-Object{$L=if($_ -is [Management.Automation.ErrorRecord]){$_.ToString()}else{$_};Write-Host $L;$w.WriteLine($L)}}" ^
 "finally{$w.Close()}"

rem O RESULTADO VEM DE UM ARQUIVO, e nao de `%ERRORLEVEL%`.
rem
rem Atravessar cmd -^> powershell -^> cmd -^> pipeline e voltar com o codigo
rem intacto depende de detalhes de aspas que variam entre versoes do PowerShell.
rem O run interno escreve o proprio resultado num arquivo e o externo le': uma
rem linha a mais, e nenhuma camada de citacao no meio.
if exist "!MARCA!" (
  set /p CODIGO=<"!MARCA!"
  del "!MARCA!" >nul 2>&1
)

rem O log foi feito para ser ENVIADO. Antes de dizer "manda esse arquivo",
rem conferir que nenhum segredo do .env vazou para dentro dele. Hoje nenhum
rem comando imprime o salt do CPF nem a senha do FTP, mas um comando novo
rem poderia, e o aviso chegaria tarde demais.
set "VAZOU="
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "K=%%a"
    set "V=%%b"
    if /I "!K!"=="RADAR_CPF_SALT"     call :procurar "!V!" "o salt do CPF"
    if /I "!K!"=="RADAR_FTP_PASSWORD" call :procurar "!V!" "a senha do FTP"
  )
)

echo.
echo ===========================================================================
if defined VAZOU (
  echo   ATENCAO: o log contem!VAZOU! - NAO envie sem apagar essa parte.
  echo.
)
if "!CODIGO!"=="0" (
  echo   TUDO CERTO.
) else (
  echo   TERMINOU COM FALHA - mande o log abaixo para o Claude:
)
echo   !LOG!
echo ===========================================================================

:fim_externo
rem A pausa existe para quem abre com dois cliques: sem ela a janela fecha antes
rem de dar tempo de ler. Quem chama de dentro de outro script - o Agendador de
rem Tarefas do Windows, por exemplo - define RADAR_SEM_PAUSA=1 e nao trava.
if not defined RADAR_SEM_PAUSA (
  echo.
  echo Pressione uma tecla para fechar...
  pause >nul
)
exit /b %CODIGO%


rem Busca literal do segredo dentro do log. `findstr /C:` nao trata o texto como
rem expressao regular, o que importa porque o salt tem `-` e `+`.
:procurar
if "%~1"=="" exit /b 0
findstr /C:"%~1" "%LOG%" >nul 2>&1 && set "VAZOU=%VAZOU% %~2"
exit /b 0


rem ===========================================================================
rem  A execucao de verdade, ja' por dentro do tee.
rem ===========================================================================
:trabalho
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "FALHAS="
set "AVISOS="

for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"dd/MM/yyyy HH:mm:ss\""') do set "INICIO=%%i"
echo ===========================================================================
echo   RADAR BRASIL - atualizacao do lake
echo   !INICIO!
echo ===========================================================================
echo.

if not exist "%PY%" (
  echo [ERRO] Ambiente virtual nao encontrado em .venv
  echo        Rode antes:  python -m venv .venv
  echo                     .venv\Scripts\pip install -e ".[dbt,dev]"
  call :marcar 1
  exit /b 1
)

rem O .env guarda o projeto do BigQuery e o salt do hash de CPF. Sem ele a carga
rem falharia mais adiante, com um erro bem menos claro que este.
if not exist ".env" (
  echo [ERRO] Arquivo .env nao encontrado.
  call :marcar 1
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

rem TOLERANTE, e nao fatal.
rem
rem A primeira versao era fatal e derrubou a atualizacao inteira porque o
rem `main` local nao tinha upstream configurado - um detalhe do git, sem
rem nenhuma relacao com o dado. Isso inverte a prioridade do projeto: o
rem snapshot do TSE e' o que NAO volta; codigo desatualizado se resolve no
rem proximo pull.
rem
rem `origin main` explicito para nao depender de `--set-upstream-to`.
set "CMD=git pull --ff-only origin main"
call :passo "Atualizar o codigo (git pull)" tolerante || goto :abortar

rem O TSE e' FATAL de proposito: ele publica apenas o ESTADO ATUAL, sem
rem historico. Um dia sem tirar a foto e' um dia que nao volta.
set "CMD="%PY%" -m ingest.tse load --ano 2026"
call :passo "TSE - candidaturas, bens, vagas, coligacoes" fatal || goto :abortar

set "CMD="%PY%" -m ingest.fotos load --ano 2026"
call :passo "Fotos oficiais" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.propostas load --ano 2026"
call :passo "Propostas de governo" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.planos load"
call :passo "Texto integral dos planos" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.legislativo load"
call :passo "Parlamentares em exercicio" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.proposicoes load"
call :passo "Atividade legislativa da Camara" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.plenario load --ano-inicio 2025 --ano-fim 2026"
call :passo "Votos e presenca em plenario" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.chapas load --ano 2026"
call :passo "Chapas - vice e suplentes" tolerante || goto :abortar

set "CMD="%PY%" -m ingest.financiamento load --ano 2026"
call :passo "Financiamento de campanha" tolerante || goto :abortar

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

rem FATAL: teste de dado que falha e' sempre erro, nunca instabilidade.
call :passo "dbt build - modelos e testes de dado" dbt || goto :abortar

set "CMD="%PY%" scripts\verificar_historico.py"
call :passo "Conferir que o historico continua la" fatal || goto :abortar

set "CMD="%PY%" -m scripts.gerar_site --saida site"
call :passo "Gerar o site" fatal || goto :abortar

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
if defined FALHAS (
  call :marcar 1
  exit /b 1
)
call :marcar 0
exit /b 0


rem ===========================================================================
rem  :abortar   uma etapa fatal falhou; encerra sem tentar as seguintes
rem ===========================================================================
:abortar
call :resumo
call :marcar 1
exit /b 1


rem ===========================================================================
rem  :marcar ^<codigo^>   grava o resultado para o run externo ler
rem ===========================================================================
:marcar
rem Os parenteses NAO sao decoracao: `echo 0>"arquivo"` faz o cmd ler `0>` como
rem redirecionamento do handle 0 (stdin), grava uma linha VAZIA e o codigo se
rem perde. Com `(echo 0)>` o argumento termina antes do redirecionador.
if defined MARCA (echo %~1)>"%MARCA%"
exit /b 0


rem ===========================================================================
rem  :passo "titulo" fatal^|dbt^|tolerante        (o comando vem em %CMD%)
rem ===========================================================================
:passo
set "TITULO=%~1"
set "MODO=%~2"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set "T0=%%i"
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
rem Devolve 1 e QUEM CHAMA decide parar, via "|| goto :abortar".
rem
rem "exit /b" dentro de uma sub-rotina chamada com "call" volta so' da
rem sub-rotina: o script seguiria para a etapa seguinte. Conferido em
rem 31/08/2026 - com a carga do TSE falhando, as 14 etapas rodaram assim mesmo.
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
if not defined AVISOS if not defined FALHAS (
  echo.
  echo   Todas as etapas concluidas sem erro.
)
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"dd/MM/yyyy HH:mm:ss\""') do (
  echo.
  echo   fim: %%i
)
echo ===========================================================================
exit /b 0
