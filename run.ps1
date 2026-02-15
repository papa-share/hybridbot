# Lancer l'application Chainlit (équivalent à make run-direct sur Windows)
# Prérequis : environnement virtuel activé (.venv\Scripts\activate)
# Usage: .\run.ps1

Set-Location $PSScriptRoot
chainlit run src/chatbot/app.py
