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
        # Obtener todas las empresas únicas
        companies = JobPosting.objects.values_list('company__name', flat=True).distinct()
        
        # Clasificar empresas por industria usando palabras clave
        industries = set()
        for company in companies:
            if not company:
                continue
            company_lower = company.lower()
            
            # Clasificación por palabras clave en el nombre de la empresa
            if any(word in company_lower for word in ['tech', 'software', 'informática', 'sistemas', 'digital', 'data', 'cloud']):
                industries.add('Tecnología')
            elif any(word in company_lower for word in ['educación', 'universidad', 'colegio', 'academia', 'instituto']):
                industries.add('Educación')
            elif any(word in company_lower for word in ['salud', 'médico', 'hospital', 'clínica', 'farmacéutico']):
                industries.add('Salud')
            elif any(word in company_lower for word in ['banco', 'financiero', 'inversión', 'seguros', 'contable']):
                industries.add('Finanzas')
            elif any(word in company_lower for word in ['retail', 'comercio', 'tienda', 'ventas', 'comercial']):
                industries.add('Retail')
            elif any(word in company_lower for word in ['manufactura', 'producción', 'industrial', 'fábrica']):
                industries.add('Manufactura')
            else:
                industries.add('Servicios')  # Default para empresas no clasificadas
        
        return list(industries) if industries else ['Servicios']
    except Exception as e:
        print(f"Error obteniendo industrias: {e}")
        return ['Servicios']

def get_modalities_from_db():
    """Obtiene modalidades únicas de la BD"""
    try:
        modalities = JobPosting.objects.exclude(work_modality__isnull=True).exclude(work_modality='').values_list('work_modality', flat=True).distinct()
        
        # Normalizar modalidades
        normalized = set()
        for mod in modalities:
            if not mod:
                continue
            mod_lower = mod.lower()
            if 'remoto' in mod_lower or 'teletrabajo' in mod_lower or 'home office' in mod_lower:
                normalized.add('Remoto')
            elif 'híbrido' in mod_lower or 'hibrido' in mod_lower or 'mixto' in mod_lower or 'combinado' in mod_lower:
                normalized.add('Híbrido')
            elif 'presencial' in mod_lower or 'oficina' in mod_lower or 'físico' in mod_lower:
                normalized.add('Presencial')
        
        return list(normalized) if normalized else []
    except Exception as e:
        print(f"Error obteniendo modalidades: {e}")
        return []

def get_areas_from_db():
    """Obtiene áreas únicas de la BD"""
    try:
        areas = JobPosting.objects.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
        return [area for area in areas if area]  # Filtrar valores vacíos
    except Exception as e:
        print(f"Error obteniendo áreas: {e}")
        return []

def get_seniorities_from_db():
    """Obtiene niveles de experiencia únicos de la BD"""
    try:
        experiences = JobPosting.objects.exclude(min_experience__isnull=True).exclude(min_experience='').values_list('min_experience', flat=True).distinct()
        
        # Normalizar experiencias
        normalized = set()
        for exp in experiences:
            if not exp:
                continue
            exp_lower = exp.lower()
            if any(word in exp_lower for word in ['junior', 'jr', 'entry', 'trainee', '0-1', '0-2', 'principiante']):
                normalized.add('Junior')
            elif any(word in exp_lower for word in ['semi', 'ssr', 'semi-senior', 'semisenior', '2-4', '3-5', 'intermedio']):
                normalized.add('Semi')
            elif any(word in exp_lower for word in ['senior', 'sr', 'experto', '5+', '6+', 'avanzado']):
                normalized.add('Senior')
        
        return list(normalized) if normalized else []
    except Exception as e:
        print(f"Error obteniendo seniorities: {e}")
        return []

def get_locations_from_db():
    """Obtiene ubicaciones únicas de la BD"""
    try:
        locations = JobPosting.objects.exclude(location__isnull=True).values_list('location__raw_text', flat=True).distinct()
        return [loc for loc in locations if loc]  # Filtrar valores vacíos
    except Exception as e:
        print(f"Error obteniendo ubicaciones: {e}")
        return []

def get_roles_from_db():
    """Obtiene roles únicos de los títulos en la BD"""
    try:
        titles = JobPosting.objects.values_list('title', flat=True).distinct()
        return [title for title in titles if title]  # Filtrar valores vacíos
    except Exception as e:
        print(f"Error obteniendo roles: {e}")
        return []

# Funciones para obtener taxonomías dinámicamente (se llaman en tiempo real)
def get_current_industries():
    """Obtiene las industrias actuales de la BD"""
    return get_industries_from_db()

def get_current_modalities():
    """Obtiene las modalidades actuales de la BD"""
    return get_modalities_from_db()

def get_current_seniorities():
    """Obtiene los seniorities actuales de la BD"""
    return get_seniorities_from_db()

def get_current_areas():
    """Obtiene las áreas actuales de la BD"""
    return get_areas_from_db()

def get_current_locations():
    """Obtiene las ubicaciones actuales de la BD"""
    return get_locations_from_db()

def get_current_roles():
    """Obtiene los roles actuales de la BD"""
    return get_roles_from_db()

def generate_dynamic_synonyms():
    """
    Genera sinónimos dinámicos basados en los datos reales de la BD.
    Esto permite que el sistema aprenda de los datos existentes.
    """
    dynamic_synonyms = {}
    
    try:
        # Obtener datos actuales
        industries = get_current_industries()
        modalities = get_current_modalities()
        seniorities = get_current_seniorities()
        areas = get_current_areas()
        locations = get_current_locations()
        roles = get_current_roles()
        
        # Generar sinónimos para modalidades
        for modality in modalities:
            if modality:
                modality_lower = modality.lower()
                if 'remoto' in modality_lower or 'teletrabajo' in modality_lower:
                    dynamic_synonyms.setdefault('remoto', []).extend(['remoto', 'teletrabajo', 'desde casa', 'home office'])
                elif 'híbrido' in modality_lower or 'hibrido' in modality_lower:
                    dynamic_synonyms.setdefault('híbrido', []).extend(['híbrido', 'hibrido', 'mixto', 'combinado'])
                elif 'presencial' in modality_lower:
                    dynamic_synonyms.setdefault('presencial', []).extend(['presencial', 'en oficina', 'oficina'])
        
        # Generar sinónimos para seniorities
        for seniority in seniorities:
            if seniority:
                seniority_lower = seniority.lower()
                if 'junior' in seniority_lower:
                    dynamic_synonyms.setdefault('junior', []).extend(['junior', 'jr', 'entry', 'trainee', 'principiante'])
                elif 'semi' in seniority_lower:
                    dynamic_synonyms.setdefault('semi', []).extend(['semi', 'ssr', 'semi-senior', 'intermedio'])
                elif 'senior' in seniority_lower:
                    dynamic_synonyms.setdefault('senior', []).extend(['senior', 'sr', 'experto', 'avanzado'])
        
        # Generar sinónimos para áreas
        for area in areas:
            if area:
                area_lower = area.lower()
                if 'datos' in area_lower or 'data' in area_lower:
                    dynamic_synonyms.setdefault('datos', []).extend(['datos', 'data', 'analítica', 'analytics'])
                elif 'desarrollo' in area_lower or 'dev' in area_lower:
                    dynamic_synonyms.setdefault('desarrollo', []).extend(['desarrollo', 'dev', 'programación', 'software'])
                elif 'diseño' in area_lower or 'design' in area_lower:
                    dynamic_synonyms.setdefault('diseño', []).extend(['diseño', 'ux', 'ui', 'diseñador'])
                elif 'calidad' in area_lower or 'qa' in area_lower:
                    dynamic_synonyms.setdefault('calidad', []).extend(['calidad', 'qa', 'testing', 'pruebas'])
        
        # Generar sinónimos para industrias basados en empresas
        companies = JobPosting.objects.values_list('company__name', flat=True).distinct()
        for company in companies:
            if company:
                company_lower = company.lower()
                if any(word in company_lower for word in ['tech', 'software', 'informática']):
                    dynamic_synonyms.setdefault('tecnología', []).extend(['tecnología', 'tech', 'informática', 'software'])
                elif any(word in company_lower for word in ['educación', 'universidad', 'colegio']):
                    dynamic_synonyms.setdefault('educación', []).extend(['educación', 'educativo', 'académico'])
                elif any(word in company_lower for word in ['salud', 'médico', 'hospital']):
                    dynamic_synonyms.setdefault('salud', []).extend(['salud', 'médico', 'hospital', 'clínica'])
        
        # Limpiar duplicados
        for key in dynamic_synonyms:
            dynamic_synonyms[key] = list(set(dynamic_synonyms[key]))
            
    except Exception as e:
        print(f"Error generando sinónimos dinámicos: {e}")
    
    return dynamic_synonyms

def get_enhanced_synonyms():
    """
    Combina los sinónimos estáticos con los dinámicos de la BD.
    """
    static_synonyms = SYNONYMS.copy()
    dynamic_synonyms = generate_dynamic_synonyms()
    
    # Combinar sinónimos estáticos y dinámicos
    enhanced_synonyms = static_synonyms.copy()
    
    for key, values in dynamic_synonyms.items():
        if key in enhanced_synonyms:
            # Combinar listas y eliminar duplicados
            enhanced_synonyms[key] = list(set(enhanced_synonyms[key] + values))
        else:
            enhanced_synonyms[key] = values
    
    return enhanced_synonyms

def _inv_synonyms() -> Dict[str,str]:
    """Genera diccionario inverso de sinónimos usando datos dinámicos de la BD"""
    inv = {}
    enhanced_synonyms = get_enhanced_synonyms()
    for canon, arr in enhanced_synonyms.items():
        for s in arr:
            inv[s.lower()] = canon
    return inv

def get_current_inv_synonyms():
    """Obtiene sinónimos inversos actuales basados en datos de BD"""
    return _inv_synonyms()

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
    
    # Obtener datos actuales de la BD
    current_industries = get_current_industries()
    current_modalities = get_current_modalities()
    current_seniorities = get_current_seniorities()
    current_areas = get_current_areas()
    current_locations = get_current_locations()
    current_inv_synonyms = get_current_inv_synonyms()
    
    # Si no se proporcionan roles, obtenerlos de la BD
    if roles_from_db is None:
        roles_from_db = get_current_roles()
    
    # Moneda + salario
    currency = "USD" if ("usd" in raw or "$" in raw) else ("CLP" if ("clp" in raw or "pesos" in raw) else None)
    salary_min = None
    nums = re.findall(r"\d[\d\.]*", raw)
    if nums:
        try: salary_min = int(nums[0].replace(".",""))
        except: salary_min = None

    include, exclude = {}, {}

    # Modalidad - usando fuzzy matching con datos de BD
    modality_matches = _fuzzy_match(raw, current_modalities, threshold=0.6)
    if modality_matches:
        include.setdefault("modality", []).extend(modality_matches)
    
    for syn, canon in current_inv_synonyms.items():
        if syn in raw and canon in ["remoto","híbrido","presencial"]:
            include.setdefault("modality", []).append({"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon])

    # Seniority - usando fuzzy matching con datos de BD
    seniority_matches = _fuzzy_match(raw, current_seniorities, threshold=0.6)
    if seniority_matches:
        include.setdefault("seniority", []).extend(seniority_matches)
    
    for syn, canon in current_inv_synonyms.items():
        if syn in raw and canon in ["junior","semi","senior"]:
            include.setdefault("seniority", []).append(canon.capitalize())

    # Industria - usando fuzzy matching con datos de BD
    industry_matches = _fuzzy_match(raw, current_industries, threshold=0.5)
    if industry_matches:
        include.setdefault("industry", []).extend(industry_matches)
    
    # También buscar por sinónimos de industrias
    for syn, canon in current_inv_synonyms.items():
        if syn in raw and canon in ["tecnología", "educación", "salud", "finanzas", "retail", "manufactura", "servicios"]:
            industry_mapping = {
                "tecnología": "Tecnología", "educación": "Educación", 
                "salud": "Salud", "finanzas": "Finanzas",
                "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
            }
            if canon in industry_mapping:
                include.setdefault("industry", []).append(industry_mapping[canon])

    # Área - usando fuzzy matching con datos de BD
    area_matches = _fuzzy_match(raw, current_areas, threshold=0.6)
    if area_matches:
        include.setdefault("area", []).extend(area_matches)
    
    for syn, canon in current_inv_synonyms.items():
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
    for syn, canon in current_inv_synonyms.items():
        if syn in raw and canon in ["data analyst","data engineer","backend developer","full stack dev","qa analyst","devops engineer","ux/ui designer"]:
            mapping = {
                "data analyst":"Data Analyst", "data engineer":"Data Engineer",
                "backend developer":"Backend Developer", "full stack dev":"Full Stack Dev",
                "qa analyst":"QA Analyst", "devops engineer":"DevOps Engineer", "ux/ui designer":"UX/UI Designer"
            }
            role_hits.append(mapping[canon])
    
    if role_hits:
        include.setdefault("role", []).extend(role_hits)

    # Ubicación - usando fuzzy matching con datos de BD
    location_matches = _fuzzy_match(raw, current_locations, threshold=0.6)
    if location_matches:
        include.setdefault("location", []).extend(location_matches)

    # Exclusiones por negación
    for term in _negations(raw):
        # role
        for r in roles_from_db:
            if _norm(r) in term:
                exclude.setdefault("role", []).append(r)
        for syn, canon in current_inv_synonyms.items():
            if syn in term and canon in ["full stack dev","backend developer","data analyst","qa analyst","devops engineer","ux/ui designer"]:
                mapping = {
                    "data analyst":"Data Analyst", "data engineer":"Data Engineer",
                    "backend developer":"Backend Developer", "full stack dev":"Full Stack Dev",
                    "qa analyst":"QA Analyst", "devops engineer":"DevOps Engineer", "ux/ui designer":"UX/UI Designer"
                }
                exclude.setdefault("role", []).append(mapping.get(canon, canon))
        # área
        for syn, canon in current_inv_synonyms.items():
            if syn in term and canon in ["datos","desarrollo","infraestructura","calidad","soporte","diseño","docencia"]:
                exclude.setdefault("area", []).append(canon.capitalize())
        # modalidad / seniority
        for syn, canon in current_inv_synonyms.items():
            if syn in term and canon in ["remoto","híbrido","presencial"]:
                exclude.setdefault("modality", []).append({"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon])
            if syn in term and canon in ["junior","semi","senior"]:
                exclude.setdefault("seniority", []).append(canon.capitalize())
        # industria
        for ind in current_industries:
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
    
    # Obtener datos actuales de la BD
    current_industries = get_current_industries()
    current_areas = get_current_areas()
    current_modalities = get_current_modalities()
    current_seniorities = get_current_seniorities()
    
    # Buscar patrones de intención
    for category, patterns in intent_patterns.items():
        for pattern in patterns:
            if re.search(pattern, raw):
                # Mapear a valores específicos usando datos de BD
                if category == "industry":
                    if any(word in raw for word in ["tecnol", "tech", "inform"]):
                        # Buscar la industria de tecnología en los datos reales
                        tech_industries = [ind for ind in current_industries if "tecnol" in ind.lower() or "tech" in ind.lower()]
                        result["industry"] = tech_industries[0] if tech_industries else "Tecnología"
                elif category == "area":
                    if any(word in raw for word in ["datos", "data", "anal"]):
                        # Buscar área de datos en los datos reales
                        data_areas = [area for area in current_areas if "datos" in area.lower() or "data" in area.lower()]
                        result["area"] = data_areas[0] if data_areas else "Datos"
                    elif any(word in raw for word in ["desarrollo", "program", "software"]):
                        # Buscar área de desarrollo en los datos reales
                        dev_areas = [area for area in current_areas if "desarrollo" in area.lower() or "dev" in area.lower()]
                        result["area"] = dev_areas[0] if dev_areas else "Desarrollo"
                    elif any(word in raw for word in ["diseño", "dise"]):
                        # Buscar área de diseño en los datos reales
                        design_areas = [area for area in current_areas if "diseño" in area.lower() or "dise" in area.lower()]
                        result["area"] = design_areas[0] if design_areas else "Diseño"
                    elif any(word in raw for word in ["qa", "calidad"]):
                        # Buscar área de calidad en los datos reales
                        qa_areas = [area for area in current_areas if "calidad" in area.lower() or "qa" in area.lower()]
                        result["area"] = qa_areas[0] if qa_areas else "Calidad"
                elif category == "modality":
                    if any(word in raw for word in ["remoto", "casa", "teletrabajo"]):
                        # Buscar modalidad remota en los datos reales
                        remote_modalities = [mod for mod in current_modalities if "remoto" in mod.lower()]
                        result["modality"] = remote_modalities[0] if remote_modalities else "Remoto"
                    elif any(word in raw for word in ["presencial", "oficina"]):
                        # Buscar modalidad presencial en los datos reales
                        onsite_modalities = [mod for mod in current_modalities if "presencial" in mod.lower()]
                        result["modality"] = onsite_modalities[0] if onsite_modalities else "Presencial"
                    elif any(word in raw for word in ["híbrido", "hibrido"]):
                        # Buscar modalidad híbrida en los datos reales
                        hybrid_modalities = [mod for mod in current_modalities if "híbrido" in mod.lower() or "hibrido" in mod.lower()]
                        result["modality"] = hybrid_modalities[0] if hybrid_modalities else "Híbrido"
                elif category == "seniority":
                    if any(word in raw for word in ["junior", "principiante"]):
                        # Buscar seniority junior en los datos reales
                        junior_seniorities = [sen for sen in current_seniorities if "junior" in sen.lower()]
                        result["seniority"] = junior_seniorities[0] if junior_seniorities else "Junior"
                    elif any(word in raw for word in ["semi", "intermedio"]):
                        # Buscar seniority semi en los datos reales
                        semi_seniorities = [sen for sen in current_seniorities if "semi" in sen.lower()]
                        result["seniority"] = semi_seniorities[0] if semi_seniorities else "Semi"
                    elif any(word in raw for word in ["senior", "experto"]):
                        # Buscar seniority senior en los datos reales
                        senior_seniorities = [sen for sen in current_seniorities if "senior" in sen.lower()]
                        result["seniority"] = senior_seniorities[0] if senior_seniorities else "Senior"
    
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

def parse_more_jobs_intent(text: str) -> dict:
    """
    Detecta si el usuario está pidiendo más empleos o diferentes empleos.
    Ejemplos: "muéstrame más", "quiero ver otros", "diferentes empleos", "más opciones"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar solicitud de más empleos
    more_patterns = [
        r"mu[eé]strame\s+m[aá]s",
        r"quiero\s+ver\s+m[aá]s",
        r"m[aá]s\s+empleos",
        r"m[aá]s\s+trabajos",
        r"m[aá]s\s+opciones",
        r"m[aá]s\s+sugerencias",
        r"diferentes\s+empleos",
        r"otros\s+empleos",
        r"m[aá]s\s+resultados",
        r"m[aá]s\s+alternativas",
        r"ver\s+m[aá]s",
        r"mostrar\s+m[aá]s",
        r"buscar\s+m[aá]s",
        r"encontrar\s+m[aá]s",
        r"generar\s+m[aá]s",
        r"dame\s+m[aá]s",
        r"dame\s+otros",
        r"dame\s+diferentes",
        r"necesito\s+m[aá]s",
        r"quiero\s+otros",
        r"quiero\s+diferentes",
        r"no\s+me\s+gustan\s+estos",
        r"estos\s+no\s+me\s+gustan",
        r"cambiar\s+opciones",
        r"nuevas\s+opciones",
        r"nuevos\s+empleos",
        r"nuevos\s+trabajos"
    ]
    
    # Buscar patrones de "más empleos"
    for pattern in more_patterns:
        if re.search(pattern, raw):
            result["action"] = "more_jobs"
            result["intent"] = "request_more"
            break
    
    # Detectar si pide específicamente diferentes empleos
    if any(word in raw for word in ["diferentes", "otros", "nuevos", "cambiar"]):
        result["variety"] = True
        # Si no se detectó action anteriormente, agregarlo
        if "action" not in result:
            result["action"] = "more_jobs"
            result["intent"] = "request_more"
    
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
        industry_matches = _fuzzy_match(raw, get_current_industries(), threshold=0.4)
        if industry_matches:
            result["industry"] = industry_matches[0]  # Tomar la primera coincidencia
    
    # Si el contexto es modalidad
    elif context == "modality":
        modality_matches = _fuzzy_match(raw, get_current_modalities(), threshold=0.4)
        if modality_matches:
            result["modality"] = modality_matches[0]
    
    # Si el contexto es seniority
    elif context == "seniority":
        seniority_matches = _fuzzy_match(raw, get_current_seniorities(), threshold=0.4)
        if seniority_matches:
            result["seniority"] = seniority_matches[0]
    
    # Si el contexto es área
    elif context == "area":
        area_matches = _fuzzy_match(raw, get_current_areas(), threshold=0.4)
        if area_matches:
            result["area"] = area_matches[0]
    
    # Si el contexto es ubicación
    elif context == "location":
        location_matches = _fuzzy_match(raw, get_current_locations(), threshold=0.4)
        if location_matches:
            result["location"] = location_matches[0]
    
    # Si no hay contexto, intentar parsear todo
    else:
        include, exclude, salary_min, currency = parse_prompt(text)
        result.update(include)
        if salary_min:
            result["salary"] = {"min": salary_min, "currency": currency}
    
    return result

def test_dynamic_system():
    """
    Función de prueba para verificar que el sistema dinámico funciona correctamente.
    """
    print("=== PRUEBA DEL SISTEMA DINÁMICO ===")
    
    try:
        # Probar obtención de datos de BD
        print("\n1. Probando obtención de datos de BD:")
        industries = get_current_industries()
        modalities = get_current_modalities()
        seniorities = get_current_seniorities()
        areas = get_current_areas()
        locations = get_current_locations()
        roles = get_current_roles()
        
        print(f"   - Industrias encontradas: {industries}")
        print(f"   - Modalidades encontradas: {modalities}")
        print(f"   - Seniorities encontrados: {seniorities}")
        print(f"   - Áreas encontradas: {areas}")
        print(f"   - Ubicaciones encontradas: {locations}")
        print(f"   - Roles encontrados: {len(roles)} roles")
        
        # Probar sinónimos dinámicos
        print("\n2. Probando sinónimos dinámicos:")
        enhanced_synonyms = get_enhanced_synonyms()
        print(f"   - Sinónimos mejorados generados: {len(enhanced_synonyms)} categorías")
        
        # Probar parsing con datos dinámicos
        print("\n3. Probando parsing con datos dinámicos:")
        test_prompts = [
            "busco trabajo remoto en tecnología",
            "quiero un empleo de datos",
            "necesito trabajo presencial",
            "busco empleo junior en desarrollo"
        ]
        
        for prompt in test_prompts:
            print(f"\n   Probando: '{prompt}'")
            include, exclude, salary, currency = parse_prompt(prompt)
            print(f"   - Include: {include}")
            print(f"   - Exclude: {exclude}")
            print(f"   - Salary: {salary}, Currency: {currency}")
        
        print("\n✅ Sistema dinámico funcionando correctamente!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en el sistema dinámico: {e}")
        return False