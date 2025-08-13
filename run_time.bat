@echo off
:LOOP
rem --- 現在の時刻（時:hh、分:mm）を取得 ---
for /F "tokens=1-2 delims=:." %%a in ("%TIME%") do (
    set /A hh=%%a
    set /A mm=%%b
)

rem --- 合計分数を計算（hh*60 + mm） ---
set /A total=hh*60 + mm

rem --- 09:00(540)～11:30(690) の範囲内なら実行 ---
if %total% GEQ 540 if %total% LEQ 690 goto RUN

rem --- 12:30(750)～15:00(900) の範囲内なら実行 ---
if %total% GEQ 750 if %total% LEQ 900 goto RUN

rem 範囲外の場合のログ出力
echo "out of time"

rem 範囲外なら1分待機して再判定
timeout /t 60 /nobreak >nul
goto LOOP

:RUN
"C:\Users\Miho\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\Miho\Documents\Python\main.py"
rem 5秒待機
timeout /t 5 /nobreak >nul
goto LOOP
