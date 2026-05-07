# Chef IA

Asistente de cocina con inteligencia artificial. Mandale tus ingredientes por texto o foto y te sugiere recetas detalladas paso a paso, con tiempos, dificultad, calorias y sustitutos para lo que te falte.

## Interfaz

La app tiene dos pantallas principales:

- **Home** — Landing page con descripcion del proyecto y acceso directo al chat.
- **Chat** — Interfaz conversacional con sidebar de historial, input de texto/foto, y panel lateral de perfil alimentario. Las recetas se muestran con chips de metadata (tiempo, dificultad, porciones, calorias, fit, dietas) y secciones coloreadas de ingredientes (verde = tenes, rojo = te faltan).

## Features

- **Recetas reales de APIs** — Busca en TheMealDB (gratis) y Spoonacular como fuentes primarias. Si las APIs devuelven menos de 3 resultados, Claude completa con su propio conocimiento.
- **Reconocimiento de fotos** — Subi una foto de tu heladera o ingredientes y la IA los identifica automaticamente.
- **Entrada por voz** — Dicta tus ingredientes con el microfono usando Web Speech API. Se transcribe a texto y se envia automaticamente. Compatible con Chrome, Edge y Safari.
- **Perfil alimentario configurable** — Panel con toggles para restricciones (celiaco, vegano, vegetariano, sin lactosa, sin frutos secos) y selectores de tiempo maximo y dificultad preferida. Se persiste en disco.
- **Conversacion con memoria** — Historial de chat por sesion con contexto completo. Sidebar con chats anteriores guardados en localStorage.
- **Recetas detalladas** — Cada receta incluye ingredientes que tenes, los que te faltan con sustitutos, paso a paso para principiantes, y consejos del chef.
- **Diseño responsive** — Funciona en desktop y mobile con sidebar colapsable y header adaptativo.

## Instalacion

### Requisitos previos

- Python 3.9+
- Una API key de [Anthropic](https://console.anthropic.com/)
- (Opcional) Una API key de [Spoonacular](https://spoonacular.com/food-api) para mas resultados de recetas

### Pasos

1. Clonar el repositorio:

```bash
git clone https://github.com/tu-usuario/agente-recetas.git
cd agente-recetas
```

2. Crear un entorno virtual (recomendado):

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Crear el archivo `.env` en la raiz del proyecto:

```
ANTHROPIC_API_KEY=tu_api_key_aqui
SPOONACULAR_API_KEY=tu_api_key_aqui
```

> `SPOONACULAR_API_KEY` es opcional. Sin ella, solo se usa TheMealDB como fuente de recetas.

5. Ejecutar la app:

```bash
python app.py
```

6. Abrir http://localhost:5000 en el navegador.

## Variables de entorno

| Variable | Requerida | Descripcion |
|---|---|---|
| `ANTHROPIC_API_KEY` | Si | API key de Anthropic para Claude |
| `SPOONACULAR_API_KEY` | No | API key de Spoonacular para recetas adicionales |

## Stack

- **Backend:** Python + Flask
- **IA:** Anthropic API (Claude claude-sonnet-4-6)
- **APIs de recetas:** TheMealDB + Spoonacular
- **Frontend:** HTML + CSS + JS vanilla (sin frameworks)
- **Markdown:** marked.js para renderizar respuestas

## Estructura del proyecto

```
agente-recetas/
├── app.py              # Servidor Flask y logica del agente
├── templates/
│   ├── home.html       # Landing page
│   └── index.html      # Interfaz de chat
├── static/
│   └── style.css       # Estilos
├── requirements.txt    # Dependencias Python
├── .env                # Variables de entorno (no incluido)
└── profile.json        # Perfil del usuario (se genera automatico)
```

## Licencia

MIT
