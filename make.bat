@echo off
REM make.bat — Windows CMD fallback when `nmake` is not available.
REM Usage: make.bat <target>
REM WHY: nmake requires Visual Studio Build Tools. Many Windows devs won't
REM have it. This .bat gives the same one-word commands via plain CMD.

IF "%1"=="install"  GOTO install
IF "%1"=="test"     GOTO test
IF "%1"=="lint"     GOTO lint
IF "%1"=="serve"    GOTO serve
IF "%1"=="run-demo" GOTO run-demo
IF "%1"=="clean"    GOTO clean

echo Usage: make.bat [install^|test^|lint^|serve^|run-demo^|clean]
GOTO end

:install
pip install -e ".[dev]"
GOTO end

:test
pytest tests\ -v --tb=short
GOTO end

:lint
ruff check gauntlet\
GOTO end

:serve
gauntlet serve
GOTO end

:run-demo
gauntlet run --goal "Summarise a news article in three bullet points" --agent-description "An LLM agent that summarises text" --mode standard --scenarios 2
GOTO end

:clean
FOR /d /r . %%d IN (__pycache__) DO @IF EXIST "%%d" rd /s /q "%%d"
DEL /s /q *.pyc 2>nul
IF EXIST gauntlet.db DEL gauntlet.db
GOTO end

:end
