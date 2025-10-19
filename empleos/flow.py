# Define los "slots" que el chat necesita y el texto de las preguntas
# Reducido a preguntas esenciales para mostrar empleos más rápido
SLOTS = [
    ("industry",  "¿En qué industria te interesa trabajar? (ej: Tecnología, Salud, Educación, Finanzas)"),
    ("area",      "¿Qué área funcional prefieres? (ej: Datos, Desarrollo, Diseño, QA)"),
    ("modality",  "¿Modalidad de trabajo? (ej: Remoto, Híbrido, Presencial)"),
    ("seniority", "¿Nivel de experiencia? (ej: Junior, Semi, Senior)"),
    # Removidas: role, location, salary, exclude - se pueden inferir o son opcionales
]

def next_missing_slot(state: dict) -> str|None:
    """Devuelve el siguiente slot no respondido, o None si ya están todos."""
    for key, _ in SLOTS:
        if key not in state or state[key] in (None, "", []):
            return key
    return None

def question_for(slot_key: str) -> str:
    for key, q in SLOTS:
        if key == slot_key:
            return q
    return "Cuéntame más de tu preferencia laboral."

def get_encouraging_response(slot_key: str, value: str) -> str:
    """Genera respuestas empáticas y alentadoras basadas en la elección del usuario."""
    responses = {
        "industry": {
            "Tecnología": "¡Excelente elección! La industria tecnológica está en constante crecimiento y ofrece muchas oportunidades. 🚀",
            "Educación": "¡Qué bonito! Trabajar en educación es muy gratificante y tiene un gran impacto social. 📚",
            "Salud": "¡Perfecto! La salud es un sector esencial y siempre en demanda. 💊",
            "Finanzas": "¡Genial! Las finanzas ofrecen estabilidad y buenas perspectivas de crecimiento. 💰",
            "Retail": "¡Muy bien! El retail es dinámico y tiene muchas oportunidades de desarrollo. 🛍️",
            "Manufactura": "¡Excelente! La manufactura es fundamental para la economía. 🏭",
            "Servicios": "¡Perfecto! Los servicios son muy diversos y ofrecen muchas posibilidades. 🎯"
        },
        "area": {
            "Datos": "¡Fantástico! Los datos son el futuro, es un área con mucha demanda. 📊",
            "Desarrollo": "¡Genial! El desarrollo de software es muy creativo y bien remunerado. 💻",
            "Diseño": "¡Excelente! El diseño es clave para crear experiencias increíbles. 🎨",
            "QA": "¡Perfecto! QA es fundamental para garantizar la calidad. ✅",
            "Infraestructura": "¡Muy bien! La infraestructura es la base de todo sistema. 🔧",
            "Soporte": "¡Genial! El soporte es esencial para el éxito de cualquier empresa. 🛠️",
            "Docencia": "¡Qué bonito! La docencia es una profesión muy noble. 👨‍🏫"
        },
        "modality": {
            "Remoto": "¡Perfecto! El trabajo remoto ofrece mucha flexibilidad y equilibrio vida-trabajo. 🏠",
            "Híbrido": "¡Excelente! Lo híbrido combina lo mejor de ambos mundos. 🏢🏠",
            "Presencial": "¡Genial! El trabajo presencial permite mayor colaboración y conexión. 🏢"
        },
        "seniority": {
            "Junior": "¡Perfecto! Todos empezamos como junior, es una gran oportunidad de aprender. 🌱",
            "Semi": "¡Excelente! El nivel semi es ideal para seguir creciendo profesionalmente. 📈",
            "Senior": "¡Fantástico! Como senior tienes mucha experiencia y valor que aportar. 🎯"
        }
    }
    
    # Buscar respuesta específica
    if slot_key in responses and value in responses[slot_key]:
        return responses[slot_key][value]
    
    # Respuestas genéricas por categoría
    generic_responses = {
        "industry": "¡Excelente elección! Esa industria tiene muchas oportunidades interesantes. 🎯",
        "area": "¡Perfecto! Esa área está muy en demanda actualmente. 💪",
        "modality": "¡Genial! Esa modalidad de trabajo es muy popular. 👍",
        "seniority": "¡Excelente! Ese nivel de experiencia es muy valorado. ⭐"
    }
    
    return generic_responses.get(slot_key, "¡Perfecto! Esa es una excelente opción. 🎉")