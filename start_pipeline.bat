@echo off
start "" /B python "C:\Users\USER\math-explorer\make-pipeline\pipeline_server.py" >> "C:\Users\USER\server.log" 2>> "C:\Users\USER\server_err.log"
timeout /t 3 /nobreak > nul
start "" /B "C:\Users\USER\ngrok.exe" http 5001 --domain backboned-diploma-snarl.ngrok-free.dev
start "" /B python -m http.server 8080 --directory "C:\Users\USER\math-explorer" >> "C:\Users\USER\math-explorer-server.log" 2>&1
