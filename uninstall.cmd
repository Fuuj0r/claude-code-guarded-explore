@echo off
rem Removes Guarded Explore and puts back any Explore agent it replaced. It asks before changing anything.
cd /d "%~dp0"
if not exist install.py (
  echo install.py is not beside this file. Unzip the whole download first: right-click the zip, choose Extract All, then run uninstall.cmd from the unzipped folder.
  echo.
  pause
  exit /b 1
)
set GUARDED_EXPLORE_NO_PAUSE=1
where py >nul 2>nul
if %errorlevel%==0 (py -3 install.py --uninstall) else (python install.py --uninstall)
if errorlevel 9009 echo Python was not found. Install Python 3.9 or later from python.org, then run this again.
echo.
pause
