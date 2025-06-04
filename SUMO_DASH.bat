@echo off
title Iniciando Pipeline de Simulacao de Trafego e Dashboard
color 0A
echo =============================================
echo.
echo    INICIANDO PIPELINE COMPLETO
echo.
echo =============================================
echo.

REM Define o diretório de trabalho do projeto
set "PROJECT_DIR=%~dp0" 
REM Se o script .bat não estiver na raiz do seu projeto, ajuste este caminho:
REM set "PROJECT_DIR=C:\Caminho\Completo\Para\Seu\Projeto"

echo Mudando para o diretorio do projeto: %PROJECT_DIR%
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo ERRO: Nao foi possivel acessar o diretorio do projeto:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)
echo Diretorio atual: %CD%
echo.

REM --- NOVO: Pergunta ao usuário ---
:USER_CHOICE
echo Deseja executar a simulacao SUMO para gerar/atualizar os dados?
echo  (S) Sim, executar a simulacao SUMO e depois gerar o dashboard.
echo  (N) Nao, pular a simulacao e tentar gerar o dashboard com dados existentes.
echo.
set /p "RUN_SIM_CHOICE=Digite S ou N e pressione Enter: "

if /I "%RUN_SIM_CHOICE%"=="S" (
    echo Opcao escolhida: Executar simulacao e dashboard.
    goto RUN_SIMULATION_STEP
) else if /I "%RUN_SIM_CHOICE%"=="N" (
    echo Opcao escolhida: Pular simulacao, ir para geracao do dashboard.
    goto PREPARE_DASHBOARD_DATA_STEP 
) else (
    echo Opcao invalida. Por favor, digite S ou N.
    echo.
    goto USER_CHOICE
)
REM --- Fim da nova seção de pergunta ---


:RUN_SIMULATION_STEP
REM --- Etapa 1: Executar o script de controle da simulação SUMO ---
echo =============================================
echo ETAPA 1: EXECUTANDO SIMULACAO SUMO (controle_semaforo.py)
echo Esta etapa pode ser interativa e o SUMO GUI sera aberto.
echo =============================================
echo.
echo Executando controle_semaforo.py...
python controle_semaforo.py
set SIM_ERRORLEVEL=%errorlevel%

echo.
echo Execucao do controle_semaforo.py finalizada com errorlevel: %SIM_ERRORLEVEL%
if %SIM_ERRORLEVEL% neq 0 (
    echo ATENCAO: controle_semaforo.py terminou com um codigo de erro. Verifique a saida acima.
)
pause
echo.

echo Verificando log de erro do SUMO (sumo_errors.log)...
if exist "sumo_errors.log" (
    for /F "usebackq" %%A in ("sumo_errors.log") do set size=%%~zA
    if defined size if %size% gtr 0 (
        echo.
        echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        echo !!! AVISO: O arquivo sumo_errors.log contem ERROS!      !!!
        echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        echo Pressione uma tecla para ver o conteudo do sumo_errors.log...
        pause
        cls
        echo --- CONTEUDO DE sumo_errors.log ---
        type "sumo_errors.log"
        echo --- FIM DE sumo_errors.log ---
        echo.
        echo Verifique o arquivo sumo_errors.log para detalhes completos.
        pause
    ) else (
        echo Log de erro do SUMO (sumo_errors.log) esta vazio ou nao foi atualizado com erros.
    )
) else (
    echo Arquivo sumo_errors.log nao encontrado (pode ser normal se o SUMO nao gerou erros).
)
echo.
pause


:PREPARE_DASHBOARD_DATA_STEP
REM --- Etapa 1.5: Preparar dados para o dashboard.py ---
echo =============================================
echo ETAPA 1.5: PREPARANDO DADOS PARA O DASHBOARD
echo =============================================
echo.
echo Procurando o arquivo JSON mais recente em 'simulation_results\' (se a simulacao foi executada)...
set "LATEST_JSON="
REM O comando dir /b /o-d lista arquivos em formato simples, ordenados por data (mais novo primeiro)
for /f "delims=" %%F in ('dir /b /o-d "simulation_results\traffic_simulation_*.json" 2^>nul') do (
    set "LATEST_JSON=%%F"
    goto found_json_for_bat_v5 
)
:found_json_for_bat_v5
if defined LATEST_JSON (
    echo JSON mais recente de 'simulation_results' encontrado: %LATEST_JSON%
    if not exist "dashboard_output\" mkdir "dashboard_output"
    echo Copiando simulation_results\%LATEST_JSON% para dashboard_output\simulation_dashboard_data.json
    copy /Y "simulation_results\%LATEST_JSON%" "dashboard_output\simulation_dashboard_data.json" >nul
    if errorlevel 1 (
        echo ERRO ao copiar o arquivo JSON de simulation_results!
        pause
    ) else (
        echo Arquivo JSON copiado de simulation_results para dashboard_output.
    )
) else (
    echo AVISO: Nenhum arquivo JSON de simulacao encontrado em 'simulation_results\'.
    echo Verificando se 'dashboard_output\simulation_dashboard_data.json' ja existe de uma execucao anterior...
)
echo.
pause

REM --- Etapa 2: Ambiente Virtual ---
echo =============================================
echo ETAPA 2: ATIVANDO AMBIENTE VIRTUAL
echo (Assumindo que dependencias como pandas e matplotlib ja estao instaladas no venv)
echo =============================================
echo.
if not exist "venv\Scripts\activate.bat" (
    echo AVISO: Ambiente virtual 'venv\Scripts\activate.bat' nao encontrado!
    echo Crie o venv e instale as dependencias (pandas, matplotlib, lxml) primeiro.
    pause
) else (
    echo Ativando ambiente virtual...
    call .\venv\Scripts\activate.bat
    echo Ambiente virtual ativado.
)
echo.
pause

REM --- Etapa 3: Verificar Arquivos de Dados para o Dashboard ---
echo =============================================
echo ETAPA 3: VERIFICANDO ARQUIVOS DE DADOS PARA O DASHBOARD
echo =============================================
echo.
set "missing_data=0"
if not exist "dashboard_output\simulation_dashboard_data.json" ( echo AVISO: dashboard_output\simulation_dashboard_data.json nao encontrado!; set "missing_data=1" )
if not exist "emission.xml" ( echo AVISO: emission.xml nao encontrado!; set "missing_data=1" )
if not exist "tripinfo.xml" ( echo AVISO: tripinfo.xml nao encontrado!; set "missing_data=1" )

if %missing_data% equ 0 ( echo Todos os arquivos de dados principais para o dashboard parecem estar presentes.)
echo.
pause

REM --- Etapa 4: Executar o Script do Dashboard ---
echo =============================================
echo ETAPA 4: GERANDO O DASHBOARD HTML (dashboard.py)
echo =============================================
echo.
echo Executando dashboard.py...
python dashboard.py
set DASH_ERRORLEVEL=%errorlevel%

if %DASH_ERRORLEVEL% neq 0 (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo !!! ERRO CRITICO na execucao do dashboard.py!           !!!
    echo !!! Errorlevel: %DASH_ERRORLEVEL%                               !!!
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    pause
) else (
    echo Geracao do dashboard HTML aparentemente concluida.
)
echo.
pause

REM --- Etapa 5: Abrir o Dashboard Gerado ---
echo =============================================
echo ETAPA 5: TENTANDO ABRIR O DASHBOARD NO NAVEGADOR
echo =============================================
echo.
set "DASHBOARD_FILE_PATH=dashboard_output_final\sumo_traffic_dashboard.html"

if exist "%DASHBOARD_FILE_PATH%" (
    echo Abrindo o relatorio final: %DASHBOARD_FILE_PATH%
    start "" "%DASHBOARD_FILE_PATH%"
    echo.
    echo Processo concluido! Relatorio deve ter sido aberto no navegador.
) else (
    echo ERRO: Arquivo do dashboard HTML (%DASHBOARD_FILE_PATH%) nao foi encontrado!
    echo Verifique o output do script dashboard.py e se os dados foram gerados corretamente.
)
echo.
echo SCRIPT .BAT FINALIZADO. Pressione qualquer tecla para fechar esta janela...
pause