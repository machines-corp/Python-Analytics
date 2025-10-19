import re
from typing import Dict, List, Tuple
from django.db.models import Q
from .models import JobPosting

SYNONYMS = {
    # Modalidades
    "remoto": ["remoto", "teletrabajo", "desde casa", "home office", "trabajo remoto", "virtual"],
    "híbrido": ["hibrido", "híbrido", "mixto", "combinado", "flexible"],
    "presencial": ["presencial", "en oficina", "oficina", "físico", "en persona"],
    
    # Seniority
    "junior": ["jr", "junior", "entry", "trainee", "principiante", "novato", "inicial"],
    "semi": ["semi", "ssr", "semi-senior", "semisenior", "intermedio", "medio"],
    "senior": ["sr", "senior", "experto", "avanzado", "experimentado", "sénior"],
    
    # Áreas
    "datos": ["datos", "data", "analítica", "analytics", "business intelligence", "bi"],
    "desarrollo": ["desarrollo", "dev", "programación", "software", "coding", "programador"],
    "infraestructura": ["infraestructura", "devops", "ops", "sistemas", "infra"],
    "calidad": ["qa", "calidad", "testing", "pruebas", "test", "aseguramiento"],
    "soporte": ["soporte", "helpdesk", "mesa de ayuda", "atención", "asistencia"],
    "diseño": ["ux", "ui", "diseño", "ux/ui", "diseñador", "interfaz", "usuario"],
    "docencia": ["docencia", "profesor", "enseñanza", "educación", "pedagogía"],
    
    # Industrias
    "tecnología": ["tecnología", "tecnologica", "tech", "tecnico", "informática", "software", "it", "sistemas"],
    "educación": ["educación", "educacion", "educativo", "académico", "universidad", "colegio"],
    "salud": ["salud", "médico", "hospital", "clínica", "sanitario", "farmacéutico"],
    "finanzas": ["finanzas", "financiero", "bancario", "contable", "economía", "inversiones"],
    "retail": ["retail", "comercio", "ventas", "tienda", "comercial"],
    "manufactura": ["manufactura", "producción", "industrial", "fábrica"],
    "servicios": ["servicios", "consultoría", "asesoría", "profesional"],

    # Roles
    "data analyst": ["analista de datos", "data analyst", "analista datos", "analista", "business analyst"],
    "data engineer": ["data engineer", "ingeniero de datos", "data engineer", "ingeniero datos"],
    "backend developer": ["backend developer", "desarrollador backend", "backend", "desarrollador back-end"],
    "full stack dev": ["full stack", "fullstack", "desarrollador full stack", "fullstack developer"],
    "qa analyst": ["qa", "analista qa", "tester", "quality assurance", "control calidad"],
    "devops engineer": ["devops", "devops engineer", "ingeniero devops", "operations"],
    "ux/ui designer": ["ux/ui", "ux ui", "diseñador ux", "diseñador ui", "ux designer", "ui designer", "diseñador"],
}

# Funciones para obtener taxonomías dinámicamente de la base de datos
def get_industries_from_db():
    """Obtiene industrias únicas de los nombres de empresas en la BD"""
    try:
        companies = JobPosting.objects.values_list('company__name', flat=True).distinct()
        # Por ahora retornamos las industrias hardcodeadas, pero podrías implementar
        # un mapeo de empresas a industrias o usar NLP para clasificar
        return ["Tecnología","Educación","Salud","Finanzas","Retail","Manufactura","Servicios"]
    except:
        return ["Tecnología","Educación","Salud","Finanzas"]

def get_modalities_from_db():
    """Obtiene modalidades únicas de la BD"""
    try:
        modalities = JobPosting.objects.exclude(work_modality__isnull=True).exclude(work_modality='').values_list('work_modality', flat=True).distinct()
        # Normalizar modalidades
        normalized = set()
        for mod in modalities:
            mod_lower = mod.lower() if mod else ''
            if 'remoto' in mod_lower or 'teletrabajo' in mod_lower:
                normalized.add('Remoto')
            elif 'híbrido' in mod_lower or 'hibrido' in mod_lower or 'mixto' in mod_lower:
                normalized.add('Híbrido')
            elif 'presencial' in mod_lower or 'oficina' in mod_lower:
                normalized.add('Presencial')
        return list(normalized) if normalized else ["Remoto","Híbrido","Presencial"]
    except:
        return ["Remoto","Híbrido","Presencial"]

def get_areas_from_db():
    """Obtiene áreas únicas de la BD"""
    try:
        areas = JobPosting.objects.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
        return list(areas) if areas else ["Datos","Desarrollo","Infraestructura","Calidad","Soporte","Diseño","Docencia","Gestión","Clínica","Apoyo","Análisis"]
    except:
        return ["Datos","Desarrollo","Infraestructura","Calidad","Soporte","Diseño","Docencia","Gestión","Clínica","Apoyo","Análisis"]

def get_seniorities_from_db():
    """Obtiene niveles de experiencia únicos de la BD"""
    try:
        experiences = JobPosting.objects.exclude(min_experience__isnull=True).exclude(min_experience='').values_list('min_experience', flat=True).distinct()
        # Normalizar experiencias
        normalized = set()
        for exp in experiences:
            exp_lower = exp.lower() if exp else ''
            if any(word in exp_lower for word in ['junior', 'jr', 'entry', 'trainee', '0-1', '0-2']):
                normalized.add('Junior')
            elif any(word in exp_lower for word in ['semi', 'ssr', 'semi-senior', 'semisenior', '2-4', '3-5']):
                normalized.add('Semi')
            elif any(word in exp_lower for word in ['senior', 'sr', 'experto', '5+', '6+']):
                normalized.add('Senior')
        return list(normalized) if normalized else ["Junior","Semi","Senior"]
    except:
        return ["Junior","Semi","Senior"]

def get_locations_from_db():
    """Obtiene ubicaciones únicas de la BD"""
    try:
        locations = JobPosting.objects.exclude(location__isnull=True).values_list('location__raw_text', flat=True).distinct()
        return list(locations) if locations else ["Chile","LatAm"]
    except:
        return ["Chile","LatAm"]

def get_roles_from_db():
    """Obtiene roles únicos de los títulos en la BD"""
    try:
        titles = JobPosting.objects.values_list('title', flat=True).distinct()
        return list(titles) if titles else []
    except:
        return []

# Obtener taxonomías dinámicamente
INDUSTRIES = get_industries_from_db()
MODALITIES = get_modalities_from_db()
SENIORITIES = get_seniorities_from_db()
AREAS = get_areas_from_db()
LOCATIONS = get_locations_from_db()

def _inv_synonyms() -> Dict[str,str]:
    inv = {}
    for canon, arr in SYNONYMS.items():
        for s in arr:
            inv[s.lower()] = canon
    return inv

INV_SYNS = _inv_synonyms()

def _norm(s: str) -> str:
    s = s.lower()
    s = s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    s = re.sub(r"[^a-z0-9\s\/\-\+\$\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _fuzzy_match(text: str, options: List[str], threshold: float = 0.6) -> List[str]:
    """
    Encuentra coincidencias aproximadas entre el texto y las opciones.
    Retorna las opciones que tienen una similitud mayor al threshold.
    """
    matches = []
    text_norm = _norm(text)
    
    for option in options:
        option_norm = _norm(option)
        
        # Coincidencia exacta
        if option_norm in text_norm or text_norm in option_norm:
            matches.append(option)
            continue
            
        # Coincidencia por palabras
        text_words = set(text_norm.split())
        option_words = set(option_norm.split())
        
        if text_words & option_words:  # Si hay palabras en común
            similarity = len(text_words & option_words) / len(text_words | option_words)
            if similarity >= threshold:
                matches.append(option)
    
    return matches

NEG_PATTERNS = [r"no\s+([a-z0-9\-/\s]+)", r"sin\s+([a-z0-9\-/\s]+)"]

def _negations(text: str) -> List[str]:
    neg = []
    for pat in NEG_PATTERNS:
        for m in re.finditer(pat, text):
            term = m.group(1).strip()
            term = re.split(r"\s+(y|o|ni|pero|,|\.)\s+", term)[0]
            neg.append(term)
    return neg

def parse_prompt(prompt: str, roles_from_db: List[str] = None) -> Tuple[dict, dict, int|None, str]:
    raw = _norm(prompt)
    
    # Si no se proporcionan roles, obtenerlos de la BD
    if roles_from_db is None:
        roles_from_db = get_roles_from_db()
    
    # Moneda + salario
    currency = "USD" if ("usd" in raw or "$" in raw) else ("CLP" if ("clp" in raw or "pesos" in raw) else None)
    salary_min = None
    nums = re.findall(r"\d[\d\.]*", raw)
    if nums:
        try: salary_min = int(nums[0].replace(".",""))
        except: salary_min = None

    include, exclude = {}, {}

    # Modalidad - usando fuzzy matching
    modality_matches = _fuzzy_match(raw, MODALITIES, threshold=0.6)
    if modality_matches:
        include.setdefault("modality", []).extend(modality_matches)
    
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["remoto","híbrido","presencial"]:
            include.setdefault("modality", []).append({"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon])

    # Seniority - usando fuzzy matching
    seniority_matches = _fuzzy_match(raw, SENIORITIES, threshold=0.6)
    if seniority_matches:
        include.setdefault("seniority", []).extend(seniority_matches)
    
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["junior","semi","senior"]:
            include.setdefault("seniority", []).append(canon.capitalize())

    # Industria - usando fuzzy matching para mejor reconocimiento
    industry_matches = _fuzzy_match(raw, INDUSTRIES, threshold=0.5)
    if industry_matches:
        include.setdefault("industry", []).extend(industry_matches)
    
    # También buscar por sinónimos de industrias
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["tecnología", "educación", "salud", "finanzas", "retail", "manufactura", "servicios"]:
            industry_mapping = {
                "tecnología": "Tecnología", "educación": "Educación", 
                "salud": "Salud", "finanzas": "Finanzas",
                "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
            }
            if canon in industry_mapping:
                include.setdefault("industry", []).append(industry_mapping[canon])

    # Área - usando fuzzy matching
    area_matches = _fuzzy_match(raw, AREAS, threshold=0.6)
    if area_matches:
        include.setdefault("area", []).extend(area_matches)
    
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["datos","desarrollo","infraestructura","calidad","soporte","diseño","docencia"]:
            include.setdefault("area", []).append(canon.capitalize())

    # Role (con sinónimos + fuzzy matching)
    role_hits = []
    
    # Fuzzy matching con roles de la BD
    if roles_from_db:
        role_matches = _fuzzy_match(raw, roles_from_db, threshold=0.5)
        role_hits.extend(role_matches)
    
    # Búsqueda exacta como fallback
    for r in roles_from_db:
        if _norm(r) in raw:
            role_hits.append(r)
    
    # Sinónimos de roles
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["data analyst","data engineer","backend developer","full stack dev","qa analyst","devops engineer","ux/ui designer"]:
            mapping = {
                "data analyst":"Data Analyst", "data engineer":"Data Engineer",
                "backend developer":"Backend Developer", "full stack dev":"Full Stack Dev",
                "qa analyst":"QA Analyst", "devops engineer":"DevOps Engineer", "ux/ui designer":"UX/UI Designer"
            }
            role_hits.append(mapping[canon])
    
    if role_hits:
        include.setdefault("role", []).extend(role_hits)

    # Ubicación - usando fuzzy matching
    location_matches = _fuzzy_match(raw, LOCATIONS, threshold=0.6)
    if location_matches:
        include.setdefault("location", []).extend(location_matches)

    # Exclusiones por negación
    for term in _negations(raw):
        # role
        for r in roles_from_db:
            if _norm(r) in term:
                exclude.setdefault("role", []).append(r)
        for syn, canon in INV_SYNS.items():
            if syn in term and canon in ["full stack dev","backend developer","data analyst","qa analyst","devops engineer","ux/ui designer"]:
                mapping = {
                    "data analyst":"Data Analyst", "data engineer":"Data Engineer",
                    "backend developer":"Backend Developer", "full stack dev":"Full Stack Dev",
                    "qa analyst":"QA Analyst", "devops engineer":"DevOps Engineer", "ux/ui designer":"UX/UI Designer"
                }
                exclude.setdefault("role", []).append(mapping.get(canon, canon))
        # área
        for syn, canon in INV_SYNS.items():
            if syn in term and canon in ["datos","desarrollo","infraestructura","calidad","soporte","diseño","docencia"]:
                exclude.setdefault("area", []).append(canon.capitalize())
        # modalidad / seniority
        for syn, canon in INV_SYNS.items():
            if syn in term and canon in ["remoto","híbrido","presencial"]:
                exclude.setdefault("modality", []).append({"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon])
            if syn in term and canon in ["junior","semi","senior"]:
                exclude.setdefault("seniority", []).append(canon.capitalize())
        # industria
        for ind in INDUSTRIES:
            if ind.lower() in term:
                exclude.setdefault("industry", []).append(ind)

    # dedup
    for d in (include, exclude):
        for k in list(d.keys()):
            d[k] = list(dict.fromkeys(d[k]))

    return include, exclude, salary_min, (currency or "USD")

def parse_complex_intent(text: str) -> dict:
    """
    Parsea intenciones complejas del usuario como:
    "me gustaría elegir un empleo tecnológico porque me gusta mucho la tecnología"
    "quiero trabajar en datos porque me interesa el análisis"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar intenciones
    intent_patterns = {
        "industry": [
            r"empleo\s+(tecnol[oó]gico|tech|inform[aá]tico)",
            r"trabajo\s+(tecnol[oó]gico|tech|inform[aá]tico)",
            r"me\s+gusta\s+(la\s+)?tecnolog[ií]a",
            r"industria\s+(tecnol[oó]gica|tech)",
            r"sector\s+(tecnol[oó]gico|tech)",
        ],
        "area": [
            r"trabajo\s+en\s+(datos|data|anal[ií]tica)",
            r"me\s+interesa\s+(datos|data|anal[ií]tica)",
            r"desarrollo\s+de\s+software",
            r"programaci[oó]n",
            r"dise[ñn]o",
            r"qa|calidad",
        ],
        "modality": [
            r"trabajo\s+(remoto|desde\s+casa)",
            r"teletrabajo",
            r"presencial",
            r"h[ií]brido",
        ],
        "seniority": [
            r"nivel\s+(junior|semi|senior)",
            r"experiencia\s+(junior|semi|senior)",
            r"principiante",
            r"experto",
        ]
    }
    
    # Buscar patrones de intención
    for category, patterns in intent_patterns.items():
        for pattern in patterns:
            if re.search(pattern, raw):
                # Mapear a valores específicos
                if category == "industry":
                    if any(word in raw for word in ["tecnol", "tech", "inform"]):
                        result["industry"] = "Tecnología"
                elif category == "area":
                    if any(word in raw for word in ["datos", "data", "anal"]):
                        result["area"] = "Datos"
                    elif any(word in raw for word in ["desarrollo", "program", "software"]):
                        result["area"] = "Desarrollo"
                    elif any(word in raw for word in ["diseño", "dise"]):
                        result["area"] = "Diseño"
                    elif any(word in raw for word in ["qa", "calidad"]):
                        result["area"] = "Calidad"
                elif category == "modality":
                    if any(word in raw for word in ["remoto", "casa", "teletrabajo"]):
                        result["modality"] = "Remoto"
                    elif any(word in raw for word in ["presencial", "oficina"]):
                        result["modality"] = "Presencial"
                    elif any(word in raw for word in ["híbrido", "hibrido"]):
                        result["modality"] = "Híbrido"
                elif category == "seniority":
                    if any(word in raw for word in ["junior", "principiante"]):
                        result["seniority"] = "Junior"
                    elif any(word in raw for word in ["semi", "intermedio"]):
                        result["seniority"] = "Semi"
                elif any(word in raw for word in ["senior", "experto"]):
                    result["seniority"] = "Senior"
    
    return result

def parse_job_selection(text: str) -> dict:
    """
    Detecta si el usuario está seleccionando un empleo específico de una lista.
    Ejemplos: "me gusta el 2", "elijo el empleo 1", "quiero el tercero"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar selección de empleos
    selection_patterns = [
        r"me\s+gusta\s+(el\s+)?(\d+)",
        r"elijo\s+(el\s+)?(\d+)",
        r"quiero\s+(el\s+)?(\d+)",
        r"selecciono\s+(el\s+)?(\d+)",
        r"el\s+(\d+)",
        r"empleo\s+(\d+)",
        r"opci[oó]n\s+(\d+)",
        r"(\d+)[oº]",
        r"primero|segundo|tercero|cuarto|quinto",
    ]
    
    # Buscar números
    numbers = re.findall(r'\d+', raw)
    if numbers:
        try:
            job_index = int(numbers[0]) - 1  # Convertir a índice 0-based
            if 0 <= job_index <= 9:  # Límite razonable
                result["selected_job_index"] = job_index
                result["action"] = "select_job"
        except ValueError:
            pass
    
    # Buscar palabras ordinales
    ordinal_map = {
        "primero": 0, "segundo": 1, "tercero": 2, 
        "cuarto": 3, "quinto": 4, "sexto": 5
    }
    
    for ordinal, index in ordinal_map.items():
        if ordinal in raw:
            result["selected_job_index"] = index
            result["action"] = "select_job"
            break
    
    return result

def parse_simple_response(text: str, context: str = None) -> dict:
    """
    Función simplificada para parsear respuestas directas del chat.
    Útil cuando el usuario responde directamente a una pregunta específica.
    """
    raw = _norm(text)
    result = {}
    
    # Si el contexto es industria
    if context == "industry":
        industry_matches = _fuzzy_match(raw, INDUSTRIES, threshold=0.4)
        if industry_matches:
            result["industry"] = industry_matches[0]  # Tomar la primera coincidencia
    
    # Si el contexto es modalidad
    elif context == "modality":
        modality_matches = _fuzzy_match(raw, MODALITIES, threshold=0.4)
        if modality_matches:
            result["modality"] = modality_matches[0]
    
    # Si el contexto es seniority
    elif context == "seniority":
        seniority_matches = _fuzzy_match(raw, SENIORITIES, threshold=0.4)
        if seniority_matches:
            result["seniority"] = seniority_matches[0]
    
    # Si el contexto es área
    elif context == "area":
        area_matches = _fuzzy_match(raw, AREAS, threshold=0.4)
        if area_matches:
            result["area"] = area_matches[0]
    
    # Si el contexto es ubicación
    elif context == "location":
        location_matches = _fuzzy_match(raw, LOCATIONS, threshold=0.4)
        if location_matches:
            result["location"] = location_matches[0]
    
    # Si no hay contexto, intentar parsear todo
    else:
        include, exclude, salary_min, currency = parse_prompt(text)
        result.update(include)
        if salary_min:
            result["salary"] = {"min": salary_min, "currency": currency}
    
    return result