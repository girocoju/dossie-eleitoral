@echo off
rem ===========================================================================
rem  Dossie Eleitoral - publicar o site na Hostinger, com a saida na tela
rem ===========================================================================
rem
rem  Uso:  publicar.bat              publica o que esta' em site\
rem        publicar.bat --gerar      gera o site antes de publicar
rem        publicar.bat --completo   reenvia TUDO, inclusive o que nao mudou
rem        publicar.bat --seco       so' lista o que subiria; nao conecta
rem
rem  O `atualizar.bat` ja' publica no fim. Este existe para as vezes em que o
rem  lake nao mudou e so' o SITE mudou - e para acompanhar uma publicacao longa
rem  de perto, que foi o caso da F-18: 20.487 arquivos numa unica execucao.
rem
rem  SO' SOBE O QUE MUDOU (ADR-039)
rem
rem  O servidor guarda um manifesto com o hash de cada arquivo. Arquivo cujo
rem  hash local bate nao sobe. Depois da F-18 a publicacao diaria e' da ordem de
rem  algumas centenas de arquivos, nao de vinte mil.
rem
rem  O manifesto sobe POR ULTIMO, e por isso uma publicacao interrompida no meio
rem  NAO deixa nada quebrado: o manifesto antigo continua no servidor, e a
rem  proxima execucao reenvia o que ficou pelo caminho. Se esta janela fechar na
rem  metade, e' seguro rodar de novo.
rem
rem  `--completo` existe para quando servidor e manifesto discordarem - alguem
rem  apagou um arquivo por FTP, por exemplo. Reenviar e' sempre seguro.
rem
rem  QUANTO TEMPO DEMORA
rem
rem  Publicacao incremental: minutos. Primeira publicacao, ou `--completo`:
rem  horas - sao 20 mil arquivos, e o servidor corta a conexao a cada ~100. A
rem  retomada e' automatica (ADR-027); reconexao no log NAO e' erro.
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
set "LOG=%~dp0logs\publicacao_!CARIMBO!.log"
set "CODIGO=1"

rem CAMINHO CURTO, e nao `%~f0` - ver o comentario equivalente em atualizar.bat.
rem Este projeto vive em "...\OneDrive\Area de Trabalho\...", com ESPACOS, e o
rem caminho atravessa cmd -^> powershell -^> cmd. `%~s0` devolve o nome 8.3, sem
rem espaco e sem acento: o problema desaparece na origem.
set "SELF=%~s0"
echo !SELF!| findstr /C:" " >nul && (
  echo [ERRO] O caminho curto ainda contem espaco:
  echo        !SELF!
  echo        Mova o projeto para uma pasta sem espacos, por exemplo
  echo        C:\dossie-eleitoral
  goto :fim_externo
)

set "ARGS=%*"
set "MARCA=%TEMP%\dossie_pub_%RANDOM%.txt"
if exist "!MARCA!" del "!MARCA!" >nul 2>&1

rem Tee em UTF-8, escrevendo na tela e no arquivo linha a linha.
rem
rem NAO e' `Tee-Object`: no PowerShell 5.1, que e' o que vem no Windows, ele
rem grava em UTF-16 e nao aceita `-Encoding`. O log sairia ilegivel em editor
rem simples e o `findstr` da trava de segredo, mais abaixo, nao acharia nada
rem dentro dele.
rem
rem `AutoFlush` e' o que faz o arquivo crescer JUNTO com a tela. Numa publicacao
rem de horas isso e' a diferenca entre acompanhar e esperar no escuro - e foi
rem exatamente o que faltou na publicacao da F-18, cuja saida ficou presa num
rem buffer ate' o fim.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$w=New-Object IO.StreamWriter($env:LOG,$false,(New-Object Text.UTF8Encoding($false)));" ^
 "$w.AutoFlush=$true;" ^
 "try{cmd /c \"$env:SELF --interno $env:ARGS\" 2>&1 | ForEach-Object{$L=if($_ -is [Management.Automation.ErrorRecord]){$_.ToString()}else{$_};Write-Host $L;$w.WriteLine($L)}}" ^
 "finally{$w.Close()}"

rem O RESULTADO VEM DE UM ARQUIVO, e nao de `%ERRORLEVEL%`: atravessar
rem cmd -^> powershell -^> cmd -^> pipeline e voltar com o codigo intacto depende
rem de detalhes de aspas que variam entre versoes do PowerShell.
if exist "!MARCA!" (
  set /p CODIGO=<"!MARCA!"
  del "!MARCA!" >nul 2>&1
)

rem O log foi feito para ser ENVIADO. A senha do FTP esta' no .env e nenhum
rem comando a imprime hoje - mas um comando novo poderia, e o aviso chegaria
rem tarde demais. Guarda que so' conhece o nome novo deixaria passar o segredo
rem gravado com o nome velho, entao os dois estao aqui.
set "VAZOU="
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "K=%%a"
    set "V=%%b"
    call :sem_bom K
    if /I "!K!"=="DOSSIE_FTP_PASSWORD" call :procurar "!V!" "a senha do FTP"
    if /I "!K!"=="RADAR_FTP_PASSWORD"  call :procurar "!V!" "a senha do FTP"
    if /I "!K!"=="DOSSIE_CPF_SALT"     call :procurar "!V!" "o salt do CPF"
    if /I "!K!"=="RADAR_CPF_SALT"      call :procurar "!V!" "o salt do CPF"
  )
)

echo.
echo ===========================================================================
if defined VAZOU (
  echo   ATENCAO: o log contem!VAZOU! - NAO envie sem apagar essa parte.
  echo.
)
rem Numa simulacao nada foi enviado, e o rodape nao pode dizer que foi. Rodape
rem que afirma mais do que aconteceu e' o mesmo erro que este projeto persegue
rem no dado: a mensagem passa a valer menos do que o silencio.
set "SECO="
echo !ARGS!| findstr /I /C:"--seco" >nul && set "SECO=1"

if "!CODIGO!"=="0" (
  if defined SECO (
    echo   SIMULACAO CONCLUIDA - nada foi enviado.
    echo   Para publicar de verdade, rode sem --seco.
  ) else (
    echo   PUBLICADO.
    echo   Confira:  https://datadubaintel.com/dossie-eleitoral/
  )
) else (
  echo   TERMINOU COM FALHA - mande o log abaixo para o Claude.
  echo.
  echo   Se a janela foi fechada ou a rede caiu no meio, rodar de novo e' seguro:
  echo   o manifesto so' sobe no fim, entao nada fica marcado como enviado por
  echo   engano.
)
echo   !LOG!
echo ===========================================================================

:fim_externo
if defined RADAR_SEM_PAUSA set "DOSSIE_SEM_PAUSA=1"
if not defined DOSSIE_SEM_PAUSA (
  echo.
  echo Pressione uma tecla para fechar...
  pause >nul
)
exit /b %CODIGO%


rem ===========================================================================
:sem_bom
rem Tira do INICIO do nome recebido (por referencia) o que nao puder comecar uma
rem chave. Um .env salvo como "UTF-8 com BOM" traz tres bytes invisiveis grudados
rem na PRIMEIRA chave; sem isto a comparacao falha, o segredo nao e' procurado no
rem log - e o rodape continua dizendo que esta' tudo certo. Guarda que para de
rem guardar sem avisar e' pior que guarda nenhum.
setlocal EnableDelayedExpansion
set "N=!%~1!"
for /l %%i in (1,1,3) do (
  set "C=!N:~0,1!"
  echo(!C!| findstr /r /c:"^[A-Za-z_#]" >nul || set "N=!N:~1!"
)
endlocal & set "%~1=%N%"
exit /b 0

:procurar
rem `findstr /C:` faz busca LITERAL, o que importa porque a senha e o salt tem
rem caracteres que uma expressao regular interpretaria.
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
set "GERAR="
set "EXTRA="

rem `%~1` e' `--interno`; os argumentos de verdade comecam no `%~2`. Sao poucos,
rem entao um `for` sobre eles e' mais claro que uma cadeia de `if`.
for %%A in (%*) do (
  if /I "%%~A"=="--gerar"   set "GERAR=1"
  if /I "%%~A"=="--completo" set "EXTRA=!EXTRA! --completo"
  if /I "%%~A"=="--seco"     set "EXTRA=!EXTRA! --dry-run"
  if /I "%%~A"=="--forcar"   set "EXTRA=!EXTRA! --forcar"
)

for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"dd/MM/yyyy HH:mm:ss\""') do set "INICIO=%%i"
echo ===========================================================================
echo   DOSSIE ELEITORAL - publicacao do site
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

rem O .env traz o projeto do BigQuery (para gerar) e as credenciais de FTP (para
rem publicar). Sem ele a falha viria mais adiante, com um erro bem menos claro.
if not exist ".env" (
  echo [ERRO] Arquivo .env nao encontrado.
  call :marcar 1
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  set "CHAVE=%%a"
  call :sem_bom CHAVE
  if not "!CHAVE!"=="" if not "!CHAVE:~0,1!"=="#" set "!CHAVE!=%%b"
)
rem Os nomes antigos seguem valendo ate' os Secrets serem renomeados.
if not defined DOSSIE_GCP_PROJECT set "DOSSIE_GCP_PROJECT=!RADAR_GCP_PROJECT!"
if not defined DOSSIE_FTP_HOST    set "DOSSIE_FTP_HOST=!RADAR_FTP_HOST!"

if not defined DOSSIE_FTP_HOST (
  echo [ERRO] As credenciais de FTP nao estao no .env.
  echo        Sem DOSSIE_FTP_HOST nao ha' onde publicar.
  call :marcar 1
  exit /b 1
)
echo   destino: !DOSSIE_FTP_HOST!
echo.

if defined GERAR (
  set "CMD="%PY%" -m scripts.gerar_site --saida site"
  call :passo "Gerar o site a partir do BigQuery" || goto :abortar
) else (
  if not exist "site\index.html" (
    echo [ERRO] A pasta site\ nao tem um site gerado.
    echo        Rode:  publicar.bat --gerar
    call :marcar 1
    exit /b 1
  )
  rem Publicar uma saida velha sem perceber e' o erro silencioso desta etapa:
  rem o site volta para um estado anterior e nada no log denuncia. A idade do
  rem index e' a pergunta certa, e a resposta cabe numa linha.
  for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Item 'site\index.html').LastWriteTime.ToString('dd/MM/yyyy HH:mm')"') do (
    echo   o site em site\ foi gerado em %%i
  )
  echo   ^(para gerar de novo antes de publicar:  publicar.bat --gerar^)
  echo.
)

rem A publicacao NAO e' tolerante como no atualizar.bat: ali ela e' a ultima de
rem quatorze etapas e o lake ja' esta' salvo. Aqui ela e' a UNICA razao de o
rem script existir, entao falhar tem de aparecer no codigo de saida.
set "CMD="%PY%" -m scripts.publicar --origem site!EXTRA!"
call :passo "Publicar na Hostinger" || goto :abortar

call :marcar 0
exit /b 0


rem ===========================================================================
:abortar
echo.
echo   A publicacao NAO foi concluida.
call :marcar 1
exit /b 1


rem ===========================================================================
rem  :marcar ^<codigo^>   grava o resultado para o run externo ler
rem ===========================================================================
:marcar
rem Os parenteses NAO sao decoracao: `echo 0>"arquivo"` faz o cmd ler `0>` como
rem redirecionamento do handle 0 (stdin), grava uma linha VAZIA e o codigo se
rem perde.
if defined MARCA (echo %~1)>"%MARCA%"
exit /b 0


rem ===========================================================================
rem  :passo "titulo"        (o comando vem em %CMD%)
rem ===========================================================================
:passo
set "TITULO=%~1"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set "T0=%%i"
echo ---------------------------------------------------------------------------
echo [!T0!] !TITULO!
echo ---------------------------------------------------------------------------
!CMD!
set "SAIDA=!ERRORLEVEL!"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set "T1=%%i"

if "!SAIDA!"=="0" (
  echo    ^> ok  ^(!T0! a !T1!^)
  echo.
  exit /b 0
)
echo    ^> FALHA ^(codigo !SAIDA!^)
echo.
rem Devolve 1 e QUEM CHAMA decide parar, via "|| goto :abortar". `exit /b` dentro
rem de uma sub-rotina chamada com `call` volta so' da sub-rotina.
exit /b 1
