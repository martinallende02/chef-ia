import os
import re
import json
import base64
import uuid
import requests
from flask import Flask, render_template, request, jsonify, session
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

client = Anthropic()

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "profile.json")

DEFAULT_PROFILE = {
    "celiaco": False,
    "vegano": False,
    "vegetariano": False,
    "intolerante_lactosa": False,
    "alergico_frutos_secos": False,
    "tiempo_maximo": "sin_limite",
    "dificultad": "cualquiera",
}

SYSTEM_PROMPT = """Sos un chef experto y asistente de cocina. El usuario te va a dar ingredientes (por texto o foto) y vos tenés que sugerir recetas detalladas.

REGLA CRITICA: NO uses emojis en ninguna parte de tu respuesta. Cero emojis. Ni en títulos, ni en secciones, ni en texto corrido. El frontend se encarga de la presentación visual.

Para CADA receta que sugieras, usá EXACTAMENTE este formato en markdown:

## [Nombre del plato]

[META] Tiempo: [X min] | Dificultad: [Fácil/Medio/Difícil] | Porciones: [N] | Calorías: [N kcal] | Fit: [Sí/No] | Dietas: [vegana, sin gluten, etc. o Ninguna]

### Ingredientes que tenés
- [ingrediente]

### Ingredientes que te faltan
- [ingrediente] - Sustituto: [alternativa]

### Paso a paso

1. [Instrucción clara y detallada con técnicas explicadas para principiantes]
2. [Siguiente paso]

### Consejos del chef
- [consejo útil sin emojis]

---

REGLAS IMPORTANTES:
- Sugerí entre 1 y 3 recetas según la cantidad de ingredientes.
- Si el usuario sube una foto, identificá los ingredientes visibles y luego sugerí recetas.
- Si no podés identificar ingredientes en la foto, pedí aclaración.
- Respondé siempre en español.
- Si el usuario hace preguntas de seguimiento sobre una receta que ya sugeriste, respondé con detalle haciendo referencia a esa receta.
- Sé amigable y motivador pero SIN emojis. Explicá las técnicas como si el usuario fuera principiante.
- Si el usuario no da suficiente información, preguntá antes de asumir.
- Cuando recibas datos de APIs de recetas (TheMealDB o Spoonacular), basá tus recetas en esa información real. NO incluyas URLs de fotos en tu respuesta.
- Si las APIs devuelven menos de 3 recetas, completá con tu conocimiento propio hasta llegar a 3. Nunca dejes al usuario sin respuesta.
- NUNCA uses emojis. Esto es fundamental."""

MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"
SPOONACULAR_BASE = "https://api.spoonacular.com"
SPOONACULAR_KEY = os.environ.get("SPOONACULAR_API_KEY", "")

# Historial en memoria por sesión
conversations = {}


# --- Perfil de usuario ---
def load_profile():
    if not os.path.exists(PROFILE_FILE):
        save_profile(DEFAULT_PROFILE)
        return DEFAULT_PROFILE.copy()
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def build_system_prompt_with_profile():
    profile = load_profile()

    restrictions = []
    labels = {
        "celiaco": "celíaco (sin gluten/TACC)",
        "vegano": "vegano (sin productos animales)",
        "vegetariano": "vegetariano (sin carne)",
        "intolerante_lactosa": "intolerante a la lactosa (sin lácteos)",
        "alergico_frutos_secos": "alérgico a frutos secos",
    }
    for key, label in labels.items():
        if profile.get(key):
            restrictions.append(label)

    tiempo = profile.get("tiempo_maximo", "sin_limite")
    dificultad = profile.get("dificultad", "cualquiera")

    has_config = restrictions or tiempo != "sin_limite" or dificultad != "cualquiera"
    if not has_config:
        return SYSTEM_PROMPT

    block = "\n\n--- PERFIL DEL USUARIO ---\n"
    if restrictions:
        block += f"Restricciones alimentarias: {', '.join(restrictions)}. NUNCA sugieras recetas que violen estas restricciones.\n"
    if tiempo != "sin_limite":
        block += f"Tiempo máximo de preparación: {tiempo}. Solo sugerí recetas que se puedan hacer en ese tiempo.\n"
    if dificultad != "cualquiera":
        block += f"Dificultad preferida: {dificultad}. Priorizá recetas de esta dificultad.\n"
    block += "Respetá siempre estas preferencias en todas tus sugerencias.\n---"

    return SYSTEM_PROMPT + block


def get_conversation_history():
    if "conversation_id" not in session:
        session["conversation_id"] = str(uuid.uuid4())
    conv_id = session["conversation_id"]
    if conv_id not in conversations:
        conversations[conv_id] = []
    return conversations[conv_id]


def extract_ingredients(message):
    """Extrae ingredientes de un mensaje del usuario."""
    cleaned = re.sub(r"[¿?!¡]", "", message.lower())
    skip_patterns = [
        r"^(hola|gracias|chau|buenas|dale|ok|sí|no|genial|perfecto)",
        r"^(qué|cómo|cuánto|puedo|se puede|es posible|hay forma)",
        r"(reemplaz|sustitu|cambiar|modificar|variante|versión)",
    ]
    for pattern in skip_patterns:
        if re.search(pattern, cleaned):
            return []

    parts = re.split(r"[,\.\;]+|\s+y\s+", cleaned)
    ingredients = []
    for part in parts:
        part = part.strip()
        part = re.sub(r"^(tengo|tenemos|hay|con|uso|tiene)\s+", "", part)
        part = re.sub(r"\s+(fresco|fresca|frescos|frescas)$", "", part)
        if part and len(part) > 2 and len(part) < 30:
            ingredients.append(part)
    return ingredients


def search_mealdb(ingredients):
    """Busca recetas en TheMealDB por ingredientes. Devuelve hasta 3 recetas con detalle completo."""
    if not ingredients:
        return []

    meal_ids = []
    for ingredient in ingredients:
        try:
            resp = requests.get(
                f"{MEALDB_BASE}/filter.php",
                params={"i": ingredient},
                timeout=5,
            )
            data = resp.json()
            if data.get("meals"):
                for meal in data["meals"][:3]:
                    if meal["idMeal"] not in meal_ids:
                        meal_ids.append(meal["idMeal"])
                break
        except (requests.RequestException, ValueError):
            continue

    if not meal_ids:
        return []

    recipes = []
    for meal_id in meal_ids[:3]:
        try:
            resp = requests.get(
                f"{MEALDB_BASE}/lookup.php",
                params={"i": meal_id},
                timeout=5,
            )
            data = resp.json()
            if data.get("meals"):
                meal = data["meals"][0]
                meal_ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f"strIngredient{i}", "")
                    measure = meal.get(f"strMeasure{i}", "")
                    if ing and ing.strip():
                        meal_ingredients.append(f"{measure.strip()} {ing.strip()}".strip())

                recipes.append({
                    "name": meal.get("strMeal", ""),
                    "category": meal.get("strCategory", ""),
                    "area": meal.get("strArea", ""),
                    "instructions": meal.get("strInstructions", ""),
                    "image": meal.get("strMealThumb", ""),
                    "ingredients": meal_ingredients,
                    "tags": meal.get("strTags", ""),
                })
        except (requests.RequestException, ValueError):
            continue

    return recipes


def search_spoonacular(ingredients, limit=3):
    """Busca recetas en Spoonacular por ingredientes. Devuelve hasta `limit` recetas."""
    if not ingredients or not SPOONACULAR_KEY:
        return []

    try:
        resp = requests.get(
            f"{SPOONACULAR_BASE}/recipes/findByIngredients",
            params={
                "ingredients": ",".join(ingredients),
                "number": limit,
                "ranking": 1,
                "apiKey": SPOONACULAR_KEY,
            },
            timeout=5,
        )
        results = resp.json()
        if not isinstance(results, list) or not results:
            return []
    except (requests.RequestException, ValueError):
        return []

    recipes = []
    for item in results:
        recipe_id = item.get("id")
        if not recipe_id:
            continue
        try:
            detail_resp = requests.get(
                f"{SPOONACULAR_BASE}/recipes/{recipe_id}/information",
                params={"apiKey": SPOONACULAR_KEY},
                timeout=5,
            )
            detail = detail_resp.json()

            sp_ingredients = []
            for ext in detail.get("extendedIngredients", []):
                original = ext.get("original", "")
                if original:
                    sp_ingredients.append(original)

            ready_min = detail.get("readyInMinutes", "")
            servings = detail.get("servings", "")

            instructions_text = ""
            analyzed = detail.get("analyzedInstructions", [])
            if analyzed:
                steps = analyzed[0].get("steps", [])
                instructions_text = "\n".join(
                    f"{s['number']}. {s['step']}" for s in steps
                )
            if not instructions_text:
                instructions_text = detail.get("instructions", "") or ""

            diets = detail.get("diets", [])
            dish_types = detail.get("dishTypes", [])

            recipes.append({
                "name": detail.get("title", ""),
                "category": ", ".join(dish_types[:2]) if dish_types else "",
                "area": ", ".join(detail.get("cuisines", [])) or "",
                "instructions": instructions_text[:1500],
                "image": detail.get("image", ""),
                "ingredients": sp_ingredients,
                "tags": ", ".join(diets) if diets else "",
                "time": f"{ready_min} min" if ready_min else "",
                "servings": str(servings) if servings else "",
                "source": "Spoonacular",
            })
        except (requests.RequestException, ValueError):
            continue

    return recipes


def search_recipes(ingredients):
    """Busca en TheMealDB primero, completa con Spoonacular hasta 3 resultados."""
    if not ingredients:
        return []

    mealdb_recipes = search_mealdb(ingredients)
    for r in mealdb_recipes:
        r["source"] = "TheMealDB"

    if len(mealdb_recipes) >= 3:
        return mealdb_recipes[:3]

    needed = 3 - len(mealdb_recipes)
    mealdb_names = {r["name"].lower() for r in mealdb_recipes}

    spoonacular_recipes = search_spoonacular(ingredients, limit=needed + 2)
    # Filtrar duplicados por nombre
    for sp in spoonacular_recipes:
        if sp["name"].lower() not in mealdb_names:
            mealdb_recipes.append(sp)
            if len(mealdb_recipes) >= 3:
                break

    return mealdb_recipes


def format_recipes_context(recipes, user_ingredients):
    """Formatea datos de las APIs como contexto para Claude."""
    if not recipes:
        return ""

    found = len(recipes)
    context = f"\n\n---\nDATOS REALES DE APIs DE RECETAS ({found} encontradas):\n"
    context += f"Ingredientes del usuario: {', '.join(user_ingredients)}\n"

    if found < 3:
        context += f"NOTA: Solo se encontraron {found} recetas en las APIs. Completá hasta 3 usando tu conocimiento propio, manteniendo el mismo formato.\n"

    for i, recipe in enumerate(recipes, 1):
        context += f"\n### Receta {i}: {recipe['name']} [Fuente: {recipe.get('source', 'API')}]\n"
        if recipe.get("category"):
            context += f"- Categoría: {recipe['category']}\n"
        if recipe.get("area"):
            context += f"- Origen: {recipe['area']}\n"
        if recipe.get("time"):
            context += f"- Tiempo: {recipe['time']}\n"
        if recipe.get("servings"):
            context += f"- Porciones: {recipe['servings']}\n"
        if recipe.get("tags"):
            context += f"- Tags/Dietas: {recipe['tags']}\n"
        context += f"- Ingredientes: {', '.join(recipe['ingredients'])}\n"
        context += f"- Instrucciones: {recipe['instructions'][:1500]}\n"

    context += "\n---\nUsá estos datos reales para armar tu respuesta. Traducí todo al español. Compará los ingredientes de cada receta con los del usuario para indicar cuáles tiene y cuáles le faltan. Si hay menos de 3 recetas de las APIs, inventá las que falten con tu conocimiento.\n"
    return context


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/chat")
def chat_page():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Mensaje vacío"}), 400

    history = get_conversation_history()

    # Buscar recetas en TheMealDB + Spoonacular
    ingredients = extract_ingredients(user_message)
    recipes = search_recipes(ingredients) if ingredients else []
    recipes_context = format_recipes_context(recipes, ingredients)

    # El historial guarda el mensaje original
    history.append({"role": "user", "content": user_message})

    # Enriquecer para Claude
    messages_for_claude = history.copy()
    if recipes_context:
        messages_for_claude[-1] = {
            "role": "user",
            "content": user_message + recipes_context,
        }

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=build_system_prompt_with_profile(),
        messages=messages_for_claude,
    )

    assistant_message = response.content[0].text
    history.append({"role": "assistant", "content": assistant_message})

    return jsonify({"response": assistant_message})


@app.route("/api/chat-image", methods=["POST"])
def chat_image():
    if "image" not in request.files:
        return jsonify({"error": "No se recibió imagen"}), 400

    image_file = request.files["image"]
    image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")

    content_type = image_file.content_type or "image/jpeg"

    text = request.form.get("message", "").strip()
    if not text:
        text = "¿Qué recetas puedo hacer con estos ingredientes?"

    history = get_conversation_history()

    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": content_type,
                "data": image_data,
            },
        },
        {"type": "text", "text": text},
    ]

    history.append({"role": "user", "content": user_content})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=build_system_prompt_with_profile(),
        messages=history,
    )

    assistant_message = response.content[0].text
    history.append({"role": "assistant", "content": assistant_message})

    return jsonify({"response": assistant_message})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    return jsonify(load_profile())


@app.route("/api/profile", methods=["POST"])
def update_profile():
    data = request.get_json()
    profile = load_profile()
    for key in DEFAULT_PROFILE:
        if key in data:
            profile[key] = data[key]
    save_profile(profile)
    return jsonify(profile)


@app.route("/api/reset", methods=["POST"])
def reset():
    """Limpiar historial de conversación"""
    if "conversation_id" in session:
        conv_id = session["conversation_id"]
        conversations.pop(conv_id, None)
    session.pop("conversation_id", None)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
