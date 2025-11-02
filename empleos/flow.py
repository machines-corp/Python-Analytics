# Define los "slots" que el chat necesita y el texto de las preguntas
# Orden de preguntas: primero lo más importante, luego detalles opcionales
SLOTS = [
    ("industry",  "¿En qué industria te interesa trabajar? (ej: Tecnología, Salud, Educación, Finanzas)"),
    ("area",      "¿Qué área funcional prefieres? (ej: Diseño, Desarrollo, Recursos Humanos)"),
    ("modality",  "¿Modalidad de trabajo? (ej: Remoto, Híbrido, Presencial)"),
    ("seniority", "¿Nivel de experiencia? (ej: Junior, Semi, Senior)"),
    ("location",  "¿En qué ciudad o región? (ej: Santiago, Valparaíso, Región Metropolitana)"),
]
# Nota: salary, accessibility y transport se detectan automáticamente del texto, no son slots obligatorios

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
            "Tecnología": "¡Excelente elección! La tecnología está en constante crecimiento. 🚀",
            "Salud": "¡Perfecto! La salud es un sector esencial. 💊",
            "Educación": "¡Qué bonito! La educación tiene un gran impacto social. 📚",
            "Finanzas": "¡Genial! Las finanzas ofrecen estabilidad. 💰",
            "Turismo": "¡Muy bien! El turismo es muy dinámico. 🌍",
            "Legal": "¡Excelente! El área legal es fundamental. ⚖️",
            "Diseño": "¡Perfecto! El diseño es clave para crear experiencias. 🎨",
            "Recursos Humanos": "¡Genial! RRHH es esencial. 👥"
        },
        "area": {
            "Turismo": "¡Excelente elección! El turismo es un sector muy dinámico con muchas oportunidades. 🌍",
            "Legal": "¡Perfecto! El área legal es fundamental y siempre en demanda. ⚖️",
            "Diseño": "¡Excelente! El diseño es clave para crear experiencias increíbles. 🎨",
            "Recursos Humanos": "¡Genial! RRHH es esencial para el crecimiento de cualquier empresa. 👥",
            "Datos": "¡Fantástico! Los datos son el futuro, es un área con mucha demanda. 📊",
            "Desarrollo": "¡Genial! El desarrollo de software es muy creativo y bien remunerado. 💻",
            "QA": "¡Perfecto! QA es fundamental para garantizar la calidad. ✅",
            "Cultura": "¡Qué bonito! La cultura es muy enriquecedora. 🎭"
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
        },
        "location": {
            "Santiago": "¡Genial! Santiago es el corazón económico del país. 🏙️",
            "Valparaíso": "¡Hermoso! Valparaíso es una ciudad con mucho encanto. ⚓",
            "Concepción": "¡Perfecto! Concepción es una ciudad universitaria. 🎓"
        },
        "salary": "Entendido, buscaré empleos con ese salario mínimo. 💵",
        "accessibility": "Perfecto, tendré en cuenta tus necesidades de accesibilidad. ♿"
    }
    
    # Buscar respuesta específica
    if slot_key in responses:
        if isinstance(responses[slot_key], dict) and value in responses[slot_key]:
            return responses[slot_key][value]
        elif isinstance(responses[slot_key], str):
            return responses[slot_key]
    
    # Respuestas genéricas por categoría
    generic_responses = {
        "industry": "¡Excelente elección de industria! 💪",
        "area": "¡Perfecto! Esa área está muy en demanda actualmente. 💪",
        "modality": "¡Genial! Esa modalidad de trabajo es muy popular. 👍",
        "seniority": "¡Excelente! Ese nivel de experiencia es muy valorado. ⭐",
        "location": "¡Genial! Buscaré empleos en esa ubicación. 📍",
        "salary": "Perfecto, buscaré empleos con buen salario. 💰",
        "accessibility": "Entendido, buscaré empleos inclusivos. ♿"
    }
    
    return generic_responses.get(slot_key, "¡Perfecto! Esa es una excelente opción. 🎉")