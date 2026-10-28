@echo off
chcp 65001 > nul
REM Ejecuta todas las pruebas de la guia (etapas 1 a 6) en Windows.
REM Uso: doble clic, o en la terminal:  probar_todo.bat

echo ===== ETAPA 1: tokens de hello =====
python analizar.py --tokens programas\hello.bzl
echo.
echo ===== ETAPA 1: arbol de hello =====
python analizar.py --arbol programas\hello.bzl
echo.
echo ===== ETAPA 1: los cinco programas =====
python analizar.py programas\hello.bzl programas\euclides.bzl programas\hanoi.bzl programas\hanoi_musical.bzl programas\all_keys.bzl
echo.
echo ===== ETAPA 1: programa con error =====
python analizar.py programas\e1_error.bzl
echo.
echo ===== ETAPA 2 =====
python bazilio_etapa2.py programas\e2_aritmetica.bzl
echo 21| python bazilio_etapa2.py programas\e2_lectura.bzl
python bazilio_etapa2.py programas\e5_division.bzl
echo.
echo ===== ETAPA 3 =====
python bazilio_etapa3.py programas\e3_control.bzl
echo.
echo ===== ETAPA 4 =====
(echo 12& echo 18)| python bazilio_etapa4.py programas\euclides.bzl
echo 3| python bazilio_etapa4.py programas\hanoi.bzl
echo Lineas de Hanoi con 10 discos:
echo 10| python bazilio_etapa4.py programas\hanoi.bzl | find /c /v ""
python bazilio_etapa4.py programas\e4_noexiste.bzl
python bazilio_etapa4.py programas\e4_parametros.bzl
echo.
echo ===== ETAPA 5 =====
python bazilio_etapa5.py programas\listas.bzl
python bazilio_etapa5.py programas\e5_notas.bzl
python bazilio_etapa5.py programas\e5_indice.bzl
echo.
echo ===== ETAPA 6 =====
python bazilio_etapa6.py programas\hello.bzl
python bazilio_etapa6.py programas\hanoi_musical.bzl Hanoi
dir /b programas\hello.*
echo.
pause
