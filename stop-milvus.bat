@echo off
chcp 65001 >nul
echo ========================================
echo    Milvus 容器停止脚本
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 docker-compose.yml 是否存在（可能在当前目录或上级目录）
if not exist "docker-compose.yml" (
    if exist "..\docker-compose.yml" (
        cd ..
    ) else (
        echo [错误] 未找到 docker-compose.yml 文件
        echo [提示] 请确保 docker-compose.yml 文件在当前目录或上级目录
        pause
        exit /b 1
    )
)

:: 检查 Docker 是否运行
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行
    pause
    exit /b 1
)

echo [1/2] 正在停止 Milvus 容器...
docker-compose stop

echo [2/2] 检查容器状态...
docker ps -a --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}" | findstr /i "milvus"

echo.
echo [完成] Milvus 容器已停止
echo.
echo 按任意键退出...
pause >nul

