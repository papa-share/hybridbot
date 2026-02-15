@echo off
REM Lancer l'application Chainlit (équivalent à make run-direct sur Windows)
REM Prérequis : environnement virtuel activé (.venv\Scripts\activate)
REM Usage: run.bat
cd /d "%~dp0"
chainlit run src/chatbot/app.py
