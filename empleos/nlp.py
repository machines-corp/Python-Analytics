import re
from typing import Dict, List, Tuple
from django.db.models import Q
from .models import JobPosting

SYNONYMS = {
    # Modalidades
    "remoto": ["remoto", "teletrabajo", "desde casa", "home office", "trabajo remoto", "virtual", "remota"],
    "híbrido": ["hibrido", "híbrido", "mixto", "combinado", "flexible"],
    "presencial": ["presencial", "en oficina", "oficina", "físico", "en persona"],
    
    # Seniority
    "junior": ["jr", "junior", "entry", "trainee", "principiante", "novato", "inicial"],
    "semi": ["semi", "ssr", "semi-senior", "semisenior", "intermedio", "medio"],
    "senior": ["sr", "senior", "experto", "avanzado", "experimentado", "sénior"],
    
    # Áreas
    "datos": ["datos", "data", "analítica", "analytics", "business intelligence"],
    "desarrollo": ["desarrollo", "dev", "programación", "software", "coding", "programador"],
    "infraestructura": ["infraestructura", "devops", "ops", "sistemas", "infra"],
    "calidad": ["qa", "calidad", "testing", "pruebas", "test", "aseguramiento"],
    "soporte": ["soporte", "helpdesk", "mesa de ayuda", "atención", "asistencia"],
    "diseño": ["ux", "ui", "diseño", "ux/ui", "diseñador", "interfaz", "usuario"],
    "gastronomía": ["gastronomía", "gastronomia", "cocina", "chef", "restaurante", "hotelería", "hoteleria"],
    "cultura": ["cultura", "biblioteca", "museo", "artes", "cultural", "patrimonio"],
    "salud": ["salud", "médico", "hospital", "clínica", "sanitario", "enfermería", "enfermeria"],
    "construcción": ["construcción", "construccion", "obra", "arquitectura", "edificación", "edificacion"],
    "transporte": ["transporte", "logística", "logistica", "transit", "vehículos", "vehiculos"],
    "turismo": ["turismo", "hoteleria", "hotelería", "viajes", "recepción", "recepcion"],
    "finanzas": ["finanzas", "financiero", "contabilidad", "contador", "auditoría", "auditoria"],
    "rrhh": ["recursos humanos", "rrhh", "hr", "talento humano", "selección", "seleccion", "reclutamiento"],
    
    # Industrias - Con sinónimos más completos
    "tecnología": ["tecnología", "tecnologica", "tech", "tecnico", "informática", "informatica", "software", "it", "sistemas", "digital", "tecnológica", "tecnologico"],
    "educación": ["educación", "educacion", "educativo", "educativa", "académico", "academico", "universidad", "colegio", "enseñanza", "enseñanza", "pedagogía", "pedagogia"],
    "salud": ["salud", "médico", "medico", "hospital", "clínica", "clinica", "sanitario", "sanitaria", "farmacéutico", "farmaceutico", "medicina", "farmacia"],
    "finanzas": ["finanzas", "financiero", "financiera", "bancario", "bancaria", "banco", "contable", "contabilidad", "economía", "economia", "inversiones", "banca", "crediticio", "crediticia", "seguros", "aseguradora"],
    "retail": ["retail", "comercio", "ventas", "tienda", "comercial", "retailer", "supermercado", "bodega", "distribución", "distribucion"],
    "manufactura": ["manufactura", "producción", "produccion", "industrial", "fábrica", "fabrica", "manufacturero", "manufacturera", "produccionista"],
    "servicios": ["servicios", "consultoría", "consultoria", "asesoría", "asesoria", "profesional", "gastronomia", "gastronomía", "gastronomica", "restaurante", "chef", "cocina", "turismo", "hotel", "viajes", "hospitalidad"],

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
            elif any(word in company_lower for word in ['educación', 'educacion', 'universidad', 'colegio', 'academia', 'instituto', 'escuela']):
                industries.add('Educación')
            elif any(word in company_lower for word in ['salud', 'medico', 'médico', 'hospital', 'clinica', 'clínica', 'farmaceutico', 'farmacéutico', 'medicina']):
                industries.add('Salud')
            elif any(word in company_lower for word in ['banco', 'financiero', 'inversion', 'inversión', 'seguros', 'contable', 'contabilidad']):
                industries.add('Finanzas')
            elif any(word in company_lower for word in ['retail', 'comercio', 'tienda', 'ventas', 'comercial', 'supermercado', 'bodega']):
                industries.add('Retail')
            elif any(word in company_lower for word in ['manufactura', 'produccion', 'producción', 'industrial', 'fabrica', 'fábrica', 'ingenieria', 'ingeniería']):
                industries.add('Manufactura')
            elif any(word in company_lower for word in ['hotel', 'turismo', 'viajes', 'gastronomia', 'gastronomía', 'restaurant', 'restaurante', 'chef', 'cocina']):
                industries.add('Servicios')  # Turismo y gastronomía son servicios
            elif any(word in company_lower for word in ['construccion', 'construcción', 'obra', 'arquitectura', 'inmobiliaria']):
                industries.add('Servicios')  # Construcción es un servicio
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
    """Obtiene áreas (industrias) únicas de la BD - campo 'area'"""
    try:
        areas = JobPosting.objects.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
        return [area for area in areas if area]  # Filtrar valores vacíos
    except Exception as e:
        print(f"Error obteniendo áreas (industrias): {e}")
        return []

def get_subareas_from_db():
    """Obtiene subáreas (áreas funcionales) únicas de la BD - campo 'subarea'"""
    try:
        subareas = JobPosting.objects.exclude(subarea__isnull=True).exclude(subarea='').values_list('subarea', flat=True).distinct()
        return [subarea for subarea in subareas if subarea]  # Filtrar valores vacíos
    except Exception as e:
        print(f"Error obteniendo subáreas (áreas funcionales): {e}")
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
    """Obtiene las áreas funcionales (subáreas) actuales de la BD
    
    IMPORTANTE: En el frontend, "área funcional" corresponde al campo 'subarea' en la BD,
    no al campo 'area' (que es para industrias).
    """
    return get_subareas_from_db()

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
    IMPORTANTE: Agrega sinónimos sin eliminar los existentes.
    """
    dynamic_synonyms = {}
    
    try:
        # Obtener datos actuales de la BD
        industries = get_current_industries()
        modalities = get_current_modalities()
        seniorities = get_current_seniorities()
        areas = get_current_areas()
        locations = get_current_locations()
        roles = get_current_roles()
        
        # 1. AGREGAR TODAS LAS ÁREAS REALES COMO SINÓNIMOS
        for area in areas:
            if area and area not in ['', None]:
                area_lower = _norm(area)
                # Agregar el nombre completo de la área como sinónimo de sí misma
                if 'datos' in area_lower or 'data' in area_lower or 'desarrollo' in area_lower:
                    dynamic_synonyms.setdefault('datos', []).append(area_lower)
                    dynamic_synonyms.setdefault('desarrollo', []).append(area_lower)
                    # También agregar palabras individuales
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('datos', []).append(word)
                            dynamic_synonyms.setdefault('desarrollo', []).append(word)
                elif 'diseño' in area_lower or 'dise' in area_lower:
                    dynamic_synonyms.setdefault('diseño', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('diseño', []).append(word)
                elif 'finanzas' in area_lower or 'contabilidad' in area_lower:
                    dynamic_synonyms.setdefault('finanzas', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('finanzas', []).append(word)
                elif 'rrhh' in area_lower or 'recursos humanos' in area_lower or 'humanos' in area_lower:
                    dynamic_synonyms.setdefault('rrhh', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('rrhh', []).append(word)
                elif 'salud' in area_lower or 'médico' in area_lower or 'medico' in area_lower:
                    dynamic_synonyms.setdefault('salud', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('salud', []).append(word)
                elif 'construcción' in area_lower or 'construccion' in area_lower:
                    dynamic_synonyms.setdefault('construcción', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('construcción', []).append(word)
                elif 'transporte' in area_lower:
                    dynamic_synonyms.setdefault('transporte', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('transporte', []).append(word)
                elif 'turismo' in area_lower:
                    dynamic_synonyms.setdefault('turismo', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('turismo', []).append(word)
                elif 'gastronomía' in area_lower or 'gastronomia' in area_lower or 'cocina' in area_lower:
                    dynamic_synonyms.setdefault('gastronomía', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('gastronomía', []).append(word)
                elif 'cultura' in area_lower:
                    dynamic_synonyms.setdefault('cultura', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('cultura', []).append(word)
                elif 'tecnología' in area_lower or 'tecnologia' in area_lower or 'tecnologica' in area_lower:
                    dynamic_synonyms.setdefault('tecnología', []).append(area_lower)
                    for word in area_lower.split():
                        if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                            dynamic_synonyms.setdefault('tecnología', []).append(word)
        
        # 2. AGREGAR SUBAREAS COMO SINÓNIMOS DE ÁREAS
        subareas = JobPosting.objects.exclude(subarea__isnull=True).exclude(subarea='').values_list('subarea', flat=True).distinct()
        subarea_to_area_map = {
            'datos': ['sistemas', 'desarrollo', 'software', 'programación', 'programacion'],
            'diseño': ['diseño gráfico', 'diseño web', 'gráfico', 'web'],
            'finanzas': ['contabilidad', 'tesorería', 'tesoreria', 'finanzas'],
            'salud': ['atención pacientes', 'atención salud', 'atencion'],
            'gastronomía': ['cocina', 'atención', 'recepción', 'recepcion'],
            'cultura': ['biblioteca', 'museos', 'biblioteca y museos'],
            'construcción': ['oficios', 'mantención', 'mantencion'],
            'transporte': ['conducción', 'reparto', 'conduccion'],
            'rrhh': ['gestión personas', 'gestión de personas', 'gestion'],
            'turismo': ['recepción', 'guía', 'recepcion', 'guia'],
        }
        
        for subarea in subareas:
            if subarea:
                subarea_lower = _norm(subarea)
                # Mapear subarea a área según palabras clave
                for area_key, keywords in subarea_to_area_map.items():
                    if any(keyword in subarea_lower for keyword in keywords):
                        dynamic_synonyms.setdefault(area_key, []).append(subarea_lower)
                        # Agregar palabras individuales
                        for word in subarea_lower.split():
                            if word not in ['de', 'y', 'la', 'el', 'los', 'las']:
                                dynamic_synonyms.setdefault(area_key, []).append(word)
                        break
        
        # 3. GENERAR SINÓNIMOS PARA MODALIDADES
        for modality in modalities:
            if modality:
                modality_lower = _norm(modality)
                if 'remoto' in modality_lower or 'teletrabajo' in modality_lower:
                    dynamic_synonyms.setdefault('remoto', []).extend([modality_lower, 'remoto', 'teletrabajo', 'desde casa', 'home office', 'telemarketing'])
                elif 'híbrido' in modality_lower or 'hibrido' in modality_lower:
                    dynamic_synonyms.setdefault('híbrido', []).extend([modality_lower, 'híbrido', 'hibrido', 'mixto', 'combinado'])
                elif 'presencial' in modality_lower:
                    dynamic_synonyms.setdefault('presencial', []).extend([modality_lower, 'presencial', 'en oficina', 'oficina', 'físico', 'fisico'])
        
        # 4. GENERAR SINÓNIMOS PARA SENIORITIES (experiencias)
        for seniority in seniorities:
            if seniority:
                seniority_lower = _norm(str(seniority))
                if 'junior' in seniority_lower or 'principiante' in seniority_lower or seniority_lower in ['0', '0 años', '1', '1 años']:
                    dynamic_synonyms.setdefault('junior', []).extend([seniority_lower, 'junior', 'jr', 'entry', 'trainee', 'principiante'])
                elif 'semi' in seniority_lower or 'intermedio' in seniority_lower or seniority_lower in ['2', '2 años', '3', '3 años']:
                    dynamic_synonyms.setdefault('semi', []).extend([seniority_lower, 'semi', 'ssr', 'semi-senior', 'intermedio'])
                elif 'senior' in seniority_lower or 'experto' in seniority_lower or seniority_lower in ['4 años', '5 años', '11 años']:
                    dynamic_synonyms.setdefault('senior', []).extend([seniority_lower, 'senior', 'sr', 'experto', 'avanzado'])
        
        # 5. GENERAR SINÓNIMOS PARA INDUSTRIAS BASADOS EN EMPRESAS Y TÍTULOS
        companies = JobPosting.objects.values_list('company__name', flat=True).distinct()
        titles = JobPosting.objects.values_list('title', flat=True).distinct()[:200]  # Limitar para performance
        
        industry_keywords = {
            'tecnología': ['tech', 'software', 'informática', 'informatica', 'sistemas', 'digital', 'it', 'sap', 'salesforce', 'desarrollador', 'programador', 'analista bi', 'arquitecto', 'pm'],
            'finanzas': ['finanzas', 'financiero', 'contabilidad', 'tesorería', 'tesoreria', 'impuestos', 'contable', 'banco', 'bancario', 'seguros', 'auditoría', 'auditoria'],
            'salud': ['salud', 'médico', 'medico', 'hospital', 'clínica', 'clinica', 'farmacia', 'farmacéutico', 'farmaceutico', 'atención salud'],
            'educación': ['educación', 'educacion', 'universidad', 'colegio', 'académico', 'academico', 'enseñanza', 'pedagogía', 'pedagogia'],
            'retail': ['retail', 'ventas', 'comercio', 'tienda', 'supermercado', 'bodega'],
            'manufactura': ['manufactura', 'producción', 'produccion', 'industrial', 'fábrica', 'fabrica', 'ingeniería', 'ingenieria'],
            'servicios': ['servicios', 'consultoría', 'consultoria', 'asesoría', 'asesoria'],
        }
        
        # Analizar empresas
        for company in companies[:100]:  # Limitar para performance
            if company:
                company_lower = _norm(company)
                for industry, keywords in industry_keywords.items():
                    if any(keyword in company_lower for keyword in keywords):
                        dynamic_synonyms.setdefault(industry, []).append(company_lower)
                        # Agregar palabras clave de la empresa (filtrar palabras irrelevantes)
                        words_to_exclude = ['spa', 'sa', 'ltda', 'sociedad', 'empresa', 'limitada', 'anónima', 'anonima', 
                                          's.a.', 's.a', 'importante', 'sector', 'del', 'servicios', 'industrial', 
                                          'industriales', 'norte', 'sur', 'chile', 'latam', 'group', 'grupo']
                        for word in company_lower.split():
                            word_clean = word.strip('.,;:()[]{}')
                            if len(word_clean) > 3 and word_clean not in words_to_exclude:
                                # Solo agregar si es relevante para la industria
                                if industry == 'finanzas' and any(kw in word_clean for kw in ['financiero', 'banco', 'seguro', 'contable']):
                                    dynamic_synonyms.setdefault(industry, []).append(word_clean)
                                elif industry == 'tecnología' and any(kw in word_clean for kw in ['tech', 'informatic', 'software', 'sistemas', 'digital', 'solucion']):
                                    dynamic_synonyms.setdefault(industry, []).append(word_clean)
                                elif industry == 'salud' and any(kw in word_clean for kw in ['salud', 'medic', 'hospital', 'clinica', 'farmacia']):
                                    dynamic_synonyms.setdefault(industry, []).append(word_clean)
                        break
        
        # Analizar títulos
        for title in titles:
            if title:
                title_lower = _norm(title)
                for industry, keywords in industry_keywords.items():
                    if any(keyword in title_lower for keyword in keywords):
                        # Agregar palabras clave relevantes del título
                        title_words = title_lower.split()
                        for word in title_words:
                            if len(word) > 3 and word not in ['para', 'con', 'desde', 'hasta', 'jornada', 'horas', 'remoto', 'presencial', 'híbrido']:
                                if industry == 'tecnología' and any(kw in word for kw in ['desarrollador', 'programador', 'analista', 'arquitecto', 'ingeniero']):
                                    dynamic_synonyms.setdefault(industry, []).append(word)
                                elif industry == 'finanzas' and any(kw in word for kw in ['contable', 'tesorería', 'finanzas', 'impuestos', 'auditor']):
                                    dynamic_synonyms.setdefault(industry, []).append(word)
        
        # Limpiar duplicados
        for key in dynamic_synonyms:
            dynamic_synonyms[key] = list(set(dynamic_synonyms[key]))
            
    except Exception as e:
        print(f"Error generando sinónimos dinámicos: {e}")
        import traceback
        traceback.print_exc()
    
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

def _is_whole_word(text: str, word: str) -> bool:
    """
    Verifica si 'word' aparece como palabra completa en 'text'.
    Usa límites de palabra para evitar coincidencias parciales (ej: 'bi' en 'biblioteca').
    """
    if not text or not word:
        return False
    # Normalizar ambos para comparar correctamente
    text_norm = _norm(text)
    word_norm = _norm(word)
    # Usar \b para límites de palabra, pero permitir que la palabra esté sola o entre espacios/palabra
    pattern = r"\b" + re.escape(word_norm) + r"\b"
    return bool(re.search(pattern, text_norm))

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
    print("\n" + "="*80)
    print("🔤 PARSE_PROMPT - Analizando prompt")
    print("="*80)
    print(f"📥 Prompt: '{prompt}'")
    
    raw = _norm(prompt)
    print(f"📝 Normalizado: '{raw}'")
    
    # Obtener datos actuales de la BD
    current_industries = get_current_industries()
    current_modalities = get_current_modalities()
    current_seniorities = get_current_seniorities()
    current_areas = get_current_areas()
    current_locations = get_current_locations()
    current_inv_synonyms = get_current_inv_synonyms()
    
    print(f"📊 Datos disponibles en BD:")
    print(f"   - Industrias: {len(current_industries)}")
    print(f"   - Modalidades: {len(current_modalities)}")
    print(f"   - Seniorities: {len(current_seniorities)}")
    print(f"   - Áreas: {len(current_areas)}")
    print(f"   - Ubicaciones: {len(current_locations)}")
    print(f"   - Sinónimos: {len(current_inv_synonyms)}")
    
    # Si no se proporcionan roles, obtenerlos de la BD
    if roles_from_db is None:
        roles_from_db = get_current_roles()
    print(f"   - Roles disponibles: {len(roles_from_db)}")
    
    # Moneda + salario
    currency = "USD" if ("usd" in raw or "$" in raw) else ("CLP" if ("clp" in raw or "pesos" in raw) else None)
    salary_min = None
    nums = re.findall(r"\d[\d\.]*", raw)
    if nums:
        try: salary_min = int(nums[0].replace(".",""))
        except: salary_min = None
    
    print(f"💰 Salario detectado: min={salary_min}, currency={currency}")

    include, exclude = {}, {}

    # Modalidad - usando fuzzy matching con datos de BD
    modality_matches = _fuzzy_match(raw, current_modalities, threshold=0.6)
    if modality_matches:
        print(f"✅ Modalidad (fuzzy): {modality_matches}")
        include.setdefault("modality", []).extend(modality_matches)
    
    # Detectar patrones específicos de modalidad: "trabajo X", "modalidad X", "tipo X"
    modality_patterns = [
        (r"(trabajo|modalidad|tipo\s+de\s+trabajo)\s+(remoto|desde\s+casa|teletrabajo|home\s+office)", "remoto"),
        (r"(trabajo|modalidad|tipo\s+de\s+trabajo)\s+(h[ií]brido|hibrido|mixto|combinado)", "híbrido"),
        (r"(trabajo|modalidad|tipo\s+de\s+trabajo)\s+(presencial|en\s+oficina|f[ií]sico)", "presencial"),
    ]
    
    for pattern, canon in modality_patterns:
        if re.search(pattern, raw):
            modality_canon = {"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon]
            if modality_canon not in include.get("modality", []):
                print(f"✅ Modalidad (patrón '{pattern}'→'{modality_canon}')")
                include.setdefault("modality", []).append(modality_canon)
                break
    
    for syn, canon in current_inv_synonyms.items():
        if _is_whole_word(raw, syn) and canon in ["remoto","híbrido","presencial"]:
            modality_canon = {"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon]
            if modality_canon not in include.get("modality", []):
                print(f"✅ Modalidad (sinónimo '{syn}'→'{canon}'→'{modality_canon}')")
                include.setdefault("modality", []).append(modality_canon)

    # Seniority - usando fuzzy matching con datos de BD
    seniority_matches = _fuzzy_match(raw, current_seniorities, threshold=0.6)
    if seniority_matches:
        print(f"✅ Seniority (fuzzy): {seniority_matches}")
        include.setdefault("seniority", []).extend(seniority_matches)
    
    # Detectar patrones específicos de seniority: "nivel X", "experiencia X", "perfil X"
    seniority_patterns = [
        (r"(nivel|experiencia|perfil|seniority)\s+(junior|jr|entry|trainee|principiante)", "junior"),
        (r"(nivel|experiencia|perfil|seniority)\s+(semi|ssr|semi-senior|semisenior|intermedio)", "semi"),
        (r"(nivel|experiencia|perfil|seniority)\s+(senior|sr|experto|avanzado)", "senior"),
    ]
    
    for pattern, canon in seniority_patterns:
        if re.search(pattern, raw):
            seniority_canon = canon.capitalize()
            if seniority_canon not in include.get("seniority", []):
                print(f"✅ Seniority (patrón '{pattern}'→'{seniority_canon}')")
                include.setdefault("seniority", []).append(seniority_canon)
                break
    
    for syn, canon in current_inv_synonyms.items():
        if _is_whole_word(raw, syn) and canon in ["junior","semi","senior"]:
            seniority_canon = canon.capitalize()
            if seniority_canon not in include.get("seniority", []):
                print(f"✅ Seniority (sinónimo '{syn}'→'{canon}'→'{seniority_canon}')")
                include.setdefault("seniority", []).append(seniority_canon)

    # Industria - usando fuzzy matching con datos de BD
    industry_matches = _fuzzy_match(raw, current_industries, threshold=0.5)
    if industry_matches:
        print(f"✅ Industria (fuzzy): {industry_matches}")
        include.setdefault("industry", []).extend(industry_matches)
    
    # También buscar por sinónimos de industrias
    for syn, canon in current_inv_synonyms.items():
        if _is_whole_word(raw, syn) and canon in ["tecnología", "educación", "salud", "finanzas", "retail", "manufactura", "servicios"]:
            industry_mapping = {
                "tecnología": "Tecnología", "educación": "Educación", 
                "salud": "Salud", "finanzas": "Finanzas",
                "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
            }
            if canon in industry_mapping:
                industry_canon = industry_mapping[canon]
                print(f"✅ Industria (sinónimo '{syn}'→'{canon}'→'{industry_canon}')")
                include.setdefault("industry", []).append(industry_canon)
    
    # Detectar patrones específicos de industria: "industria X", "sector X", "trabajo de la industria X"
    industry_patterns = [
        (r"industria\s+(tecnol[oó]gica|tech|inform[aá]tica|digital)", "tecnología"),
        (r"industria\s+(educativa|educacional|de\s+educaci[oó]n)", "educación"),
        (r"industria\s+(de\s+)?salud|sector\s+salud|industria\s+m[eé]dica", "salud"),
        (r"industria\s+(financiera|bancaria|de\s+finanzas|del\s+sector\s+financiero)", "finanzas"),
        (r"industria\s+(financiero|bancario|finanzas)", "finanzas"),  # Variante sin género
        (r"trabajo\s+de\s+(la\s+)?industria\s+(financiera|bancaria|finanzas)", "finanzas"),
        (r"sector\s+(financiero|bancario|finanzas)", "finanzas"),
        (r"industria\s+(comercial|retail|de\s+ventas)", "retail"),
        (r"industria\s+(manufacturera|industrial|de\s+producci[oó]n)", "manufactura"),
        (r"industria\s+de\s+servicios|sector\s+servicios", "servicios"),
    ]
    
    for pattern, canon in industry_patterns:
        if re.search(pattern, raw):
            industry_mapping = {
                "tecnología": "Tecnología", "educación": "Educación", 
                "salud": "Salud", "finanzas": "Finanzas",
                "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
            }
            if canon in industry_mapping:
                industry_canon = industry_mapping[canon]
                if industry_canon not in include.get("industry", []):
                    print(f"✅ Industria (patrón '{pattern}'→'{industry_canon}')")
                    include.setdefault("industry", []).append(industry_canon)
                break  # Solo tomar el primer match

    # Área - PRIMERO buscar coincidencia exacta o muy cercana en BD antes de usar mapeo estático
    area_matches = _fuzzy_match(raw, current_areas, threshold=0.6)
    exact_area_matches = []
    partial_area_matches = []
    
    # Buscar coincidencias exactas primero (sin mapeo)
    raw_lower = raw.lower()
    raw_has_datos = 'datos' in raw_lower or 'data' in raw_lower
    
    for area in current_areas:
        area_lower = _norm(area).lower()
        area_has_datos = 'datos' in area_lower or 'data' in area_lower
        
        # Coincidencia exacta (ignorar mayúsculas)
        if raw_lower == area_lower:
            exact_area_matches.append(area)
        # Si el área contiene "datos" pero el usuario no lo mencionó, NO considerarlo exacto
        elif area_has_datos and not raw_has_datos:
            # No incluir áreas con "datos" si el usuario solo dijo "desarrollo"
            continue
        # Si el usuario mencionó "datos", incluir áreas que lo contengan
        elif raw_has_datos and area_has_datos:
            if _is_whole_word(area_lower, raw_lower.replace('datos', '').replace('data', '').strip()):
                exact_area_matches.append(area)
        # Para otras coincidencias de palabra completa
        elif _is_whole_word(area_lower, raw_lower) and not area_has_datos:
            exact_area_matches.append(area)
    
    # Si encontramos coincidencias exactas, usarlas
    if exact_area_matches:
        # Filtrar para evitar duplicados y preferir áreas sin "datos" si el usuario no lo mencionó
        filtered_matches = []
        if not raw_has_datos:
            # Priorizar áreas sin "datos"
            solo_desarrollo = [a for a in exact_area_matches if 'datos' not in _norm(a).lower()]
            if solo_desarrollo:
                filtered_matches = solo_desarrollo
            else:
                filtered_matches = exact_area_matches
        else:
            filtered_matches = exact_area_matches
        
        print(f"✅ Área (coincidencia exacta filtrada): {filtered_matches}")
        include.setdefault("area", []).extend(filtered_matches)
    elif area_matches:
        # Filtrar matches para evitar "Desarrollo / datos" cuando el usuario dice solo "desarrollo"
        for match in area_matches:
            match_lower = _norm(match).lower()
            match_has_datos = 'datos' in match_lower or 'data' in match_lower
            
            # Si el usuario NO mencionó "datos" pero el match lo contiene, NO incluirlo
            if not raw_has_datos and match_has_datos:
                # NO incluir áreas con "datos" si el usuario no lo mencionó
                print(f"   ⏭️  Saltando '{match}' porque contiene 'datos' pero el usuario no lo mencionó")
                continue
            
            # Si el usuario mencionó "datos", incluir matches que lo contengan
            if raw_has_datos and match_has_datos:
                partial_area_matches.append(match)
            # Si el match no contiene "datos", incluirlo
            elif not match_has_datos:
                partial_area_matches.append(match)
        
        if partial_area_matches:
            print(f"✅ Área funcional (fuzzy filtrado): {partial_area_matches}")
            include.setdefault("area", []).extend(partial_area_matches)
        elif area_matches:
            # Si todos fueron filtrados, usar los matches pero advertir
            print(f"⚠️  Área funcional (todos los matches filtrados, usando todos): {area_matches}")
            include.setdefault("area", []).extend(area_matches)
    
    # Detectar patrones específicos de área: "área X", "trabajo en X", "funcional X"
    area_patterns = [
        (r"área\s+(funcional\s+)?(datos|data|anal[ií]tica)", "datos", True),  # Solo datos, no desarrollo
        (r"área\s+(funcional\s+)?desarrollo", "desarrollo", False),  # Solo desarrollo
        (r"trabajo\s+en\s+(datos|data|anal[ií]tica)", "datos", True),
        (r"trabajo\s+en\s+desarrollo", "desarrollo", False),
        (r"área\s+(funcional\s+)?(dise[ñn]o|ux|ui)", "diseño", False),
        (r"trabajo\s+en\s+(dise[ñn]o|ux|ui)", "diseño", False),
        (r"área\s+(funcional\s+)?(calidad|qa|testing|pruebas)", "calidad", False),
        (r"área\s+(funcional\s+)?(finanzas|financiero|contabilidad)", "finanzas", False),
        (r"área\s+(funcional\s+)?(recursos\s+humanos|rrhh|hr)", "rrhh", False),
    ]
    
    # Mapeo mejorado: separar desarrollo de datos
    area_mapping_exact = {
        "datos": ["Desarrollo / datos"],  # Solo si dice específicamente "datos"
        "desarrollo": [],  # Para desarrollo, buscar en BD primero
        "diseño": ["Diseño"],
        "calidad": ["Servicios Generales"],
        "finanzas": ["Finanzas"],
        "rrhh": ["Recursos Humanos"],
    }
    
    for pattern, canon, is_data_specific in area_patterns:
        if re.search(pattern, raw):
            if canon == "desarrollo":
                # Para desarrollo, buscar áreas que contengan "desarrollo" pero no necesariamente "datos"
                dev_areas = [a for a in current_areas if 'desarrollo' in _norm(a).lower()]
                solo_desarrollo = [a for a in dev_areas if 'datos' not in _norm(a).lower()]
                
                if solo_desarrollo:
                    # Si hay un área que es solo "desarrollo" (sin "datos"), usar esa
                    for area in solo_desarrollo:
                        if area not in include.get("area", []):
                            print(f"✅ Área (patrón desarrollo→'{area}')")
                            include.setdefault("area", []).append(area)
                    break
                elif dev_areas and not raw_has_datos:
                    # Si solo hay áreas con "datos" pero el usuario no mencionó "datos", 
                    # priorizar áreas que contengan "desarrollo" pero no "datos"
                    # Si no hay ninguna, NO agregar nada aquí (se maneja arriba con fuzzy matching)
                    solo_dev = [a for a in dev_areas if 'datos' not in _norm(a).lower()]
                    if solo_dev:
                        for area in solo_dev:
                            if area not in include.get("area", []):
                                print(f"✅ Área funcional (patrón desarrollo→'{area}')")
                                include.setdefault("area", []).append(area)
                    # Si no hay áreas sin "datos", no agregar nada (dejar que fuzzy matching lo maneje)
                    break
                elif dev_areas:
                    # Si el usuario mencionó "datos" o no hay otra opción, usar "Desarrollo / datos"
                    for area in dev_areas:
                        if area not in include.get("area", []):
                            print(f"✅ Área (patrón desarrollo→'{area}')")
                            include.setdefault("area", []).append(area)
                    break
            elif canon in area_mapping_exact:
                areas_to_add = area_mapping_exact[canon]
                for area_canon in areas_to_add:
                    if area_canon not in include.get("area", []):
                        print(f"✅ Área (patrón '{pattern}'→'{area_canon}')")
                        include.setdefault("area", []).append(area_canon)
                break
    
    # Mapping de sinónimos canónicos a nombres reales de áreas en la BD
    # IMPORTANTE: Separar desarrollo de datos
    area_mapping = {
        "datos": ["Desarrollo / datos"],  # Solo si dice específicamente "datos"
        "desarrollo": [],  # Se maneja arriba buscando en BD
        "infraestructura": ["Tecnología"],
        "calidad": ["Servicios Generales"],
        "soporte": ["Servicios Generales"],
        "diseño": ["Diseño"],
        "gastronomía": ["Gastronomía"],
        "cultura": ["Cultura"],
        "salud": ["Salud"],
        "construcción": ["Construcción"],
        "transporte": ["Transporte"],
        "turismo": ["Turismo"],
        "finanzas": ["Finanzas"],
        "rrhh": ["Recursos Humanos"],
        "tecnología": ["Tecnología"],
    }
    
    for syn, canon in current_inv_synonyms.items():
        if _is_whole_word(raw, syn) and canon in area_mapping:
            # Para desarrollo, buscar en BD (subáreas/áreas funcionales) en lugar de usar mapeo estático
            if canon == "desarrollo" and canon not in [p[1] for p in area_patterns if re.search(p[0], raw)]:
                # Buscar en subáreas (áreas funcionales) que contengan "desarrollo"
                dev_areas = [a for a in current_areas if 'desarrollo' in _norm(a).lower()]
                if dev_areas:
                    # Si el usuario no mencionó "datos", priorizar áreas sin "datos"
                    if not raw_has_datos:
                        solo_desarrollo = [a for a in dev_areas if 'datos' not in _norm(a).lower()]
                        if solo_desarrollo:
                            dev_areas = solo_desarrollo
                        else:
                            # Si no hay áreas sin "datos", NO agregar nada
                            print(f"   ⏭️  Saltando sinónimo 'desarrollo'→'Desarrollo / datos' porque el usuario no mencionó 'datos' y no hay otras opciones")
                            continue
                    
                    for area in dev_areas:
                        if area not in include.get("area", []):
                            print(f"✅ Área funcional (sinónimo desarrollo→'{area}')")
                            include.setdefault("area", []).append(area)
            elif area_mapping[canon]:
                for area_canon in area_mapping[canon]:
                    if area_canon not in include.get("area", []):
                        print(f"✅ Área (sinónimo '{syn}'→'{canon}'→'{area_canon}')")
                        include.setdefault("area", []).append(area_canon)

    # Role (con sinónimos + fuzzy matching)
    role_hits = []
    
    # Fuzzy matching con roles de la BD
    if roles_from_db:
        role_matches = _fuzzy_match(raw, roles_from_db, threshold=0.5)
        if role_matches:
            print(f"✅ Role (fuzzy): {role_matches[:3]}...")  # Mostrar solo primeros 3
        role_hits.extend(role_matches)
    
    # Búsqueda exacta como fallback
    for r in roles_from_db:
        if _norm(r) in raw:
            role_hits.append(r)
    
    # Sinónimos de roles
    for syn, canon in current_inv_synonyms.items():
        if _is_whole_word(raw, syn) and canon in ["data analyst","data engineer","backend developer","full stack dev","qa analyst","devops engineer","ux/ui designer"]:
            mapping = {
                "data analyst":"Data Analyst", "data engineer":"Data Engineer",
                "backend developer":"Backend Developer", "full stack dev":"Full Stack Dev",
                "qa analyst":"QA Analyst", "devops engineer":"DevOps Engineer", "ux/ui designer":"UX/UI Designer"
            }
            role_mapped = mapping[canon]
            print(f"✅ Role (sinónimo '{syn}'→'{canon}'→'{role_mapped}')")
            role_hits.append(role_mapped)
    
    if role_hits:
        # Eliminar duplicados
        unique_role_hits = list(dict.fromkeys(role_hits))
        print(f"✅ Roles detectados: {unique_role_hits[:3]}...")  # Mostrar solo primeros 3
        include.setdefault("role", []).extend(unique_role_hits)

    # Ubicación - usando fuzzy matching con datos de BD
    location_matches = _fuzzy_match(raw, current_locations, threshold=0.6)
    if location_matches:
        print(f"✅ Ubicación (fuzzy): {location_matches}")
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

    # Detectar accesibilidad y transporte
    accessibility_keywords = ["accesibilidad", "silla de ruedas", "discapacidad", "incluyente", "inclusivo", "rampa", "ascensor", "baño accesible", "transport accesible"]
    transport_keywords = ["transporte", "bus", "metro", "movi", "terminal", "transantiago", "red"]
    
    if any(keyword in raw for keyword in accessibility_keywords):
        include.setdefault("accessibility", []).append(True)
        print(f"✅ Accesibilidad detectada")
    
    if any(keyword in raw for keyword in transport_keywords):
        include.setdefault("transport", []).append(True)
        print(f"✅ Transporte detectado")

    # dedup
    for d in (include, exclude):
        for k in list(d.keys()):
            d[k] = list(dict.fromkeys(d[k]))

    print(f"\n✅ Resultado final de parse_prompt:")
    print(f"   - include: {include}")
    print(f"   - exclude: {exclude}")
    print(f"   - salary_min: {salary_min}")
    print(f"   - currency: {currency or 'USD'}")
    print("="*80)
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

def parse_change_slot_intent(text: str) -> dict:
    """
    Detecta si el usuario quiere cambiar un slot específico.
    Ejemplos: "cambiar industria", "quiero cambiar el área", "modificar la modalidad", "cambiar a tecnología"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar cambio de slot
    change_patterns = {
        "industry": [
            r"cambiar\s+(la\s+)?industria",
            r"cambiar\s+(el\s+)?sector",
            r"modificar\s+(la\s+)?industria",
            r"cambiar\s+industria\s+a\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+a\s+([a-záéíóúñ\s]+)\s+industria",
            r"quiero\s+cambiar\s+(la\s+)?industria",
            r"cambiar\s+industria\s+por\s+([a-záéíóúñ\s]+)",
            r"prefiero\s+([a-záéíóúñ\s]+)\s+industria",
            r"otra\s+industria",
            r"diferente\s+industria",
        ],
        "area": [
            r"cambiar\s+(el\s+)?area",
            r"cambiar\s+(la\s+)?area",
            r"modificar\s+(el\s+)?area",
            r"cambiar\s+area\s+a\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+area\s+por\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+(el\s+)?area\s+funcional",
            r"quiero\s+cambiar\s+(el\s+)?area",
            r"otra\s+area",
            r"diferente\s+area",
            r"prefiero\s+([a-záéíóúñ\s]+)\s+area",
        ],
        "modality": [
            r"cambiar\s+(la\s+)?modalidad",
            r"modificar\s+(la\s+)?modalidad",
            r"cambiar\s+modalidad\s+a\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+modalidad\s+por\s+([a-záéíóúñ\s]+)",
            r"quiero\s+cambiar\s+(la\s+)?modalidad",
            r"otra\s+modalidad",
            r"diferente\s+modalidad",
            r"prefiero\s+([a-záéíóúñ\s]+)\s+modalidad",
        ],
        "seniority": [
            r"cambiar\s+(el\s+)?nivel",
            r"cambiar\s+(la\s+)?experiencia",
            r"modificar\s+(el\s+)?nivel",
            r"cambiar\s+seniority",
            r"cambiar\s+nivel\s+a\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+experiencia\s+a\s+([a-záéíóúñ\s]+)",
            r"quiero\s+cambiar\s+(el\s+)?nivel",
            r"otro\s+nivel",
            r"diferente\s+nivel",
        ],
        "location": [
            r"cambiar\s+(la\s+)?ubicacion",
            r"cambiar\s+(la\s+)?ciudad",
            r"modificar\s+(la\s+)?ubicacion",
            r"cambiar\s+ubicacion\s+a\s+([a-záéíóúñ\s]+)",
            r"cambiar\s+ubicacion\s+por\s+([a-záéíóúñ\s]+)",
            r"quiero\s+cambiar\s+(la\s+)?ubicacion",
            r"otra\s+ubicacion",
            r"diferente\s+ubicacion",
            r"sin\s+ubicacion",
            r"sin\s+restriccion\s+de\s+ubicacion",
        ],
    }
    
    # Buscar patrones de cambio
    for slot_key, patterns in change_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, raw)
            if match:
                result["action"] = "change_slot"
                result["slot"] = slot_key
                # Si hay un valor nuevo en el patrón, intentar extraerlo
                if match.groups() and match.group(1):
                    result["new_value"] = match.group(1).strip()
                return result
    
    # También detectar cuando el usuario dice directamente un valor nuevo sin mencionar "cambiar"
    # pero el contexto indica que quiere cambiar (ej: si dice "tecnología" cuando ya tiene industria)
    # Esto se manejará en _merge_state_with_prompt cuando haya un slot en modo "changing"
    
    return result

def parse_show_jobs_intent(text: str) -> dict:
    """
    Detecta si el usuario quiere ver empleos ahora.
    Ejemplos: "muéstrame empleos", "quiero ver trabajos", "buscar ahora", "muéstrame resultados"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar solicitud de mostrar empleos
    show_patterns = [
        r"mu[eé]strame\s+(los\s+)?empleos",
        r"mu[eé]strame\s+(los\s+)?trabajos",
        r"quiero\s+ver\s+(los\s+)?empleos",
        r"quiero\s+ver\s+(los\s+)?trabajos",
        r"buscar\s+(ahora|empleos|trabajos)",
        r"mu[eé]strame\s+(los\s+)?resultados",
        r"buscar\s+(los\s+)?empleos",
        r"buscar\s+(los\s+)?trabajos",
        r"encontrar\s+(los\s+)?empleos",
        r"dame\s+(los\s+)?empleos",
        r"dame\s+(los\s+)?trabajos",
        r"quiero\s+ver\s+resultados",
        r"mu[eé]strame\s+(las\s+)?opciones",
        r"ver\s+(los\s+)?empleos",
        r"ver\s+(los\s+)?trabajos",
        r"listo",
        r"listo,\s+mu[eé]strame",
        r"ya\s+es\s+suficiente",
        r"ya\s+est[aá]\s+bien",
    ]
    
    # Buscar patrones de "mostrar empleos"
    for pattern in show_patterns:
        if re.search(pattern, raw):
            result["action"] = "show_jobs"
            result["intent"] = "request_show"
            return result
    
    return result

def parse_more_jobs_intent(text: str) -> dict:
    """
    Detecta si el usuario está pidiendo más empleos o diferentes empleos.
    Ejemplos: "muéstrame más", "quiero ver otros", "diferentes empleos", "más opciones", "buscar"
    """
    raw = _norm(text)
    result = {}
    
    # Patrones para detectar solicitud de más empleos
    more_patterns = [
        r"^buscar$",  # Solo "buscar"
        r"^buscar\s+empleos?$",
        r"^buscar\s+trabajos?$",
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
        r"nuevos\s+trabajos",
        r"siguiente\s+p[aá]gina",
        r"continuar\s+buscando"
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
    
    # Obtener sinónimos actuales para búsqueda
    current_inv_synonyms = get_current_inv_synonyms()
    
    # Si el contexto es industria
    if context == "industry":
        # Detectar patrones como "industria X", "sector X", "trabajo de la industria X"
        industry_patterns = [
            (r"industria\s+(tecnol[oó]gica|tech|inform[aá]tica|digital)", "tecnología"),
            (r"industria\s+(educativa|educacional|de\s+educaci[oó]n)", "educación"),
            (r"industria\s+(de\s+)?salud|sector\s+salud|industria\s+m[eé]dica", "salud"),
            (r"industria\s+(financiera|bancaria|de\s+finanzas|del\s+sector\s+financiero)", "finanzas"),
            (r"industria\s+(financiero|bancario|finanzas)", "finanzas"),
            (r"trabajo\s+de\s+(la\s+)?industria\s+(financiera|bancaria|finanzas)", "finanzas"),
            (r"sector\s+(financiero|bancario|finanzas)", "finanzas"),
            (r"industria\s+(comercial|retail|de\s+ventas)", "retail"),
            (r"industria\s+(manufacturera|industrial|de\s+producci[oó]n)", "manufactura"),
            (r"industria\s+de\s+servicios|sector\s+servicios", "servicios"),
        ]
        
        for pattern, canon in industry_patterns:
            if re.search(pattern, raw):
                industry_mapping = {
                    "tecnología": "Tecnología", "educación": "Educación", 
                    "salud": "Salud", "finanzas": "Finanzas",
                    "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
                }
                if canon in industry_mapping:
                    result["industry"] = industry_mapping[canon]
                    return result  # Retornar inmediatamente si encontramos un patrón
        
        # Si el usuario escribió algo como "industria X", extraer X
        raw_words = raw.split()
        if len(raw_words) > 1 and "industria" in raw_words:
            # Remover palabras como "industria", "de", "la", "del" y trabajar con el resto
            words_to_remove = ["industria", "de", "la", "del", "las", "los", "el", "un", "una"]
            text_to_match = " ".join([w for w in raw_words if w not in words_to_remove])
            raw = text_to_match
        
        # También extraer después de "sector"
        if "sector" in raw_words:
            words_to_remove = ["sector", "de", "la", "del", "las", "los", "el", "un", "una"]
            text_to_match = " ".join([w for w in raw_words if w not in words_to_remove])
            if text_to_match:
                raw = text_to_match
        
        # Primero intentar con sinónimos
        for syn, canon in current_inv_synonyms.items():
            if _is_whole_word(raw, syn) and canon in ["tecnología", "educación", "salud", "finanzas", "retail", "manufactura", "servicios"]:
                industry_mapping = {
                    "tecnología": "Tecnología", "educación": "Educación", 
                    "salud": "Salud", "finanzas": "Finanzas",
                    "retail": "Retail", "manufactura": "Manufactura", "servicios": "Servicios"
                }
                if canon in industry_mapping:
                    result["industry"] = industry_mapping[canon]
                    break
        
        # Si no se encontró con sinónimos, intentar fuzzy matching
        if not result.get("industry"):
            industry_matches = _fuzzy_match(raw, get_current_industries(), threshold=0.4)
            if industry_matches:
                result["industry"] = industry_matches[0]
    
    # Si el contexto es modalidad
    elif context == "modality":
        # Primero intentar con sinónimos
        for syn, canon in current_inv_synonyms.items():
            if _is_whole_word(raw, syn) and canon in ["remoto","híbrido","presencial"]:
                modality_canon = {"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon]
                result["modality"] = modality_canon
                break
        
        # Si no se encontró con sinónimos, intentar fuzzy matching
        if not result.get("modality"):
            modality_matches = _fuzzy_match(raw, get_current_modalities(), threshold=0.4)
            if modality_matches:
                result["modality"] = modality_matches[0]
    
    # Si el contexto es seniority
    elif context == "seniority":
        # Primero intentar con sinónimos
        for syn, canon in current_inv_synonyms.items():
            if _is_whole_word(raw, syn) and canon in ["junior","semi","senior"]:
                result["seniority"] = canon.capitalize()
                break
        
        # Si no se encontró con sinónimos, intentar fuzzy matching
        if not result.get("seniority"):
            seniority_matches = _fuzzy_match(raw, get_current_seniorities(), threshold=0.4)
            if seniority_matches:
                result["seniority"] = seniority_matches[0]
    
    # Si el contexto es área
    elif context == "area":
        # Extraer solo la palabra clave si hay preposiciones
        raw_words = raw.split()
        words_to_remove = ["área", "de", "la", "el", "del", "las", "los", "funcional", "me", "gusta", "mas", "más"]
        keywords = [w for w in raw_words if w not in words_to_remove]
        raw_clean = " ".join(keywords) if keywords else raw
        
        # PRIMERO: Buscar coincidencia exacta en BD
        current_areas = get_current_areas()
        raw_clean_lower = _norm(raw_clean).lower()
        
        # Buscar coincidencia exacta o que contenga la palabra clave
        exact_matches = []
        for area in current_areas:
            area_lower = _norm(area).lower()
            if raw_clean_lower == area_lower:
                exact_matches.append(area)
            elif _is_whole_word(area_lower, raw_clean_lower):
                exact_matches.append(area)
        
        if exact_matches:
            # Priorizar áreas que NO contengan "datos" si el usuario no lo mencionó
            if 'datos' not in raw_clean_lower:
                solo_desarrollo = [a for a in exact_matches if 'datos' not in _norm(a).lower()]
                if solo_desarrollo:
                    result["area"] = solo_desarrollo[0]
                else:
                    result["area"] = exact_matches[0]
            else:
                result["area"] = exact_matches[0]
        
        # Si no hay coincidencia exacta, usar fuzzy matching pero filtrar
        if not result.get("area"):
            area_matches = _fuzzy_match(raw_clean, current_areas, threshold=0.5)
            if area_matches:
                # Si el usuario dijo "desarrollo" sin "datos", evitar "Desarrollo / datos"
                if 'desarrollo' in raw_clean_lower and 'datos' not in raw_clean_lower:
                    filtered_matches = [a for a in area_matches if 'datos' not in _norm(a).lower()]
                    if filtered_matches:
                        result["area"] = filtered_matches[0]
                    else:
                        # Si no hay otra opción y todos fueron filtrados, no asignar área funcional
                        # (el usuario puede haber querido decir algo diferente)
                        print(f"   ⏭️  No se asignó área funcional porque el usuario dijo 'desarrollo' sin 'datos' y no hay subáreas que coincidan")
                else:
                    result["area"] = area_matches[0]
        
        # Fallback: usar sinónimos solo si no se encontró nada
        if not result.get("area"):
            area_mapping = {
                "datos": "Desarrollo / datos",
                "desarrollo": None,  # Se maneja arriba con búsqueda en BD
                "infraestructura": "Tecnología",
                "calidad": "Servicios Generales",
                "soporte": "Servicios Generales",
                "diseño": "Diseño",
                "gastronomía": "Gastronomía",
                "cultura": "Cultura",
                "salud": "Salud",
                "construcción": "Construcción",
                "transporte": "Transporte",
                "turismo": "Turismo",
                "finanzas": "Finanzas",
                "rrhh": "Recursos Humanos",
                "tecnología": "Tecnología",
            }
            
            for syn, canon in current_inv_synonyms.items():
                if _is_whole_word(raw_clean, syn) and canon in area_mapping:
                    mapped_area = area_mapping[canon]
                    if mapped_area:
                        result["area"] = mapped_area
                        break
                    elif canon == "desarrollo":
                        # Para desarrollo, buscar en BD
                        dev_areas = [a for a in current_areas if 'desarrollo' in _norm(a).lower()]
                        if dev_areas:
                            # Preferir áreas que no tengan "datos" si el usuario no lo mencionó
                            if 'datos' not in raw_clean_lower:
                                solo_dev = [a for a in dev_areas if 'datos' not in _norm(a).lower()]
                                if solo_dev:
                                    result["area"] = solo_dev[0]
                                else:
                                    # Si no hay área solo "desarrollo" y el usuario no mencionó "datos", no asignar
                                    print(f"   ⏭️  No se asignó área funcional porque el usuario dijo 'desarrollo' sin 'datos' y no hay subáreas que coincidan")
                            else:
                                result["area"] = dev_areas[0]
                            break
    
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