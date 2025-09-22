# Define los "slots" que el chat necesita y el texto de las preguntas
SLOTS = [
    ("industry",  "¿En qué industria te interesa trabajar? (Tecnología, Educación, Salud, Finanzas)"),
    ("area",      "¿Qué área funcional prefieres? (Datos, Desarrollo, Docencia, Infraestructura, QA, Soporte, Diseño...)"),
    ("role",      "¿Algún cargo específico? (p.ej., Data Analyst, Backend Developer, Profesor de Historia)"),
    ("seniority", "¿Nivel de experiencia? (Junior, Semi, Senior)"),
    ("modality",  "¿Modalidad de trabajo? (Remoto, Híbrido, Presencial)"),
    ("location",  "¿Ubicación preferida? (Chile, LatAm o ciudad)"),
    ("salary",    "¿Salario mínimo deseado? (número y moneda, p.ej. 1500 USD o 1.200.000 CLP)"),
    ("exclude",   "¿Hay algo que NO quieres? (p.ej., no full stack, no QA)"),
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