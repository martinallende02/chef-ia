# Agente de Recetas — Instrucciones para Claude Code

## El Proyecto
App web tipo chat donde el usuario manda texto o foto con ingredientes 
y recibe recetas detalladas. Backend Python/Flask + Frontend HTML/CSS/JS.

## Stack
- Backend: Python + Flask
- IA: Anthropic API (claude-sonnet-4-6)
- Frontend: HTML + CSS + JS (sin frameworks)
- Variables de entorno: python-dotenv (.env ya configurado)

## Estructura de archivos
- app.py → servidor Flask y lógica del agente
- templates/index.html → interfaz de chat
- static/style.css → estilos
- .env → ANTHROPIC_API_KEY (ya existe, no tocar)

## Reglas
- Siempre planificá antes de codear
- Nunca marques algo como listo sin probarlo
- Código simple y legible, sin sobreingeniería
- Comentá las partes importantes en español