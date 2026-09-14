@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ===============================================
echo   Xuong Dung Video Tu Dong - Khoi dong
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python tren may nay.
    echo Hay cai Python tai: https://www.python.org/downloads/
    echo Luu y quan trong: khi cai dat, nho TICK CHON o "Add Python to PATH".
    echo Cai xong thi mo lai file nay (CHAY_UNG_DUNG.bat).
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist venv (
    echo Dang tao moi truong Python rieng cho ung dung nay ^(chi lam 1 lan duy nhat^)...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Dang kiem tra / cai thu vien can thiet...
echo ^(Lan dau chay se lau hon vi phai tai ve, cac lan sau se rat nhanh^)
pip install --quiet --disable-pip-version-check -r requirements.txt

where ffmpeg >nul 2>nul
if errorlevel 1 (
    if exist ffmpeg_bin\ffmpeg.exe (
        set "PATH=%~dp0ffmpeg_bin;%PATH%"
    ) else (
        echo.
        echo Khong thay ffmpeg tren may - dang tu dong tai ban di dong ve...
        echo ^(chi 1 lan duy nhat, dung luong khoang 90MB, can co Internet^)
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg_temp.zip' } catch { exit 1 }"
        if exist ffmpeg_temp.zip (
            echo Dang giai nen ffmpeg...
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'ffmpeg_temp.zip' -DestinationPath 'ffmpeg_extract' -Force"
            if not exist ffmpeg_bin mkdir ffmpeg_bin
            for /d %%D in (ffmpeg_extract\ffmpeg-*) do (
                copy "%%D\bin\*.exe" ffmpeg_bin\ >nul
            )
            del ffmpeg_temp.zip >nul 2>nul
            rmdir /s /q ffmpeg_extract >nul 2>nul
            set "PATH=%~dp0ffmpeg_bin;%PATH%"
        ) else (
            echo.
            echo [LOI] May khong tu tai duoc ffmpeg ^(co the do mang^).
            echo Hay tu tai tai: https://www.gyan.dev/ffmpeg/builds/  ^(chon ban "release essentials"^)
            echo Giai nen ra, vao thu muc con ten "bin", copy 3 file .exe trong do
            echo dan vao thu muc "ffmpeg_bin" ngay ben canh file nay, roi chay lai file nay.
            echo.
            pause
            exit /b 1
        )
    )
)

echo.
echo Moi thu da san sang. Dang khoi dong may chu...
echo Trinh duyet se tu mo sau vai giay - dung tat cua so den nay khi dang dung app.
echo.
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"
python app.py

pause
