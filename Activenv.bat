@echo off
REM Active le venv paddleocr et ouvre l’invite de commande au bon endroit
cd /d c:\Ba7ath_scripts\B_trad
call venv-paddleocr\Scripts\activate
REM Lancer le script de traduction
REM python trad_pdf.py
REM Pause pour garder le terminal ouvert
cmd
