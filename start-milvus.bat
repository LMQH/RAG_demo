@echo off
chcp 65001 >nul
echo ========================================
echo    Milvus 容器启动脚本
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Docker 是否运行
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

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

echo [1/3] 检查 Milvus 容器状态...
docker ps -a --filter "name=milvus" --format "{{.Names}}" | findstr /i "milvus" >nul
if %errorlevel% equ 0 (
    echo [2/3] 发现已存在的 Milvus 容器，正在启动...
    docker-compose up -d
) else (
    echo [2/3] 未发现 Milvus 容器，正在创建并启动...
    docker-compose up -d
)

:: 等待容器启动
echo [3/3] 等待 Milvus 服务启动...
timeout /t 5 /nobreak >nul

:: 检查容器状态
docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr /i "milvus"
if %errorlevel% equ 0 (
    echo.
    echo [成功] Milvus 容器已启动！
    echo [信息] Milvus 服务地址: localhost:19530
    echo.
) else (
    echo.
    echo [警告] 容器可能未正常启动，请检查日志: docker-compose logs
    echo.
)

echo 按任意键退出...
pause >nul

