from typing import Tuple, List, Dict
from .models import JobPosting
from django.db.models import Q

def _seniority_to_experience_range(seniority: str):
    """
    Convierte un seniority a rango de años de experiencia.
    """
    seniority_lower = seniority.lower().strip()
    
    if seniority_lower in ['junior', 'jr']:
        return [0, 1, 2]  # 0-2 años
    elif seniority_lower in ['semi', 'ssr', 'semi-senior', 'semisenior']:
        return [2, 3, 4, 5]  # 2-5 años
    elif seniority_lower in ['senior', 'sr']:
        return [5, 6, 7, 8, 9, 10]  # 5+ años
    else:
        return []

def _apply(queryset, include:dict, exclude:dict, salary_min:int|None, currency:str|None):
    qs = queryset
    
    print(f"\n🔧 _APPLY - Aplicando filtros")
    print(f"   - Queryset inicial: {qs.count()} empleos")
    
    # Mapeo de campos del modelo Job a JobPosting
    # IMPORTANTE: En el frontend:
    #   - "industria" → campo `area` en BD (ej: "Tecnología", "Servicios Generales")
    #   - "área funcional" → campo `subarea` en BD (ej: "Desarrollo de Software", "Contabilidad y Tesorería")
    field_mapping = {
        'industry': 'area',        # Industry se mapea a area (ej: "Tecnología" → area="Tecnología")
        'area': 'subarea',         # Area funcional se mapea a subarea (ej: "Desarrollo de Software" → subarea="Desarrollo de Software")
        'role': 'title',           # Mapear role a title
        'seniority': 'min_experience',  # Mapear seniority a min_experience
        'modality': 'work_modality',
        'location': 'location__raw_text',
        'currency': 'salary_text',  # Para salario usaremos salary_text
        'accessibility': 'accessibility_mentioned',
        'transport': 'transport_mentioned',
    }
    
    # salario - por ahora no aplicamos filtro de salario ya que JobPosting usa salary_text
    # TODO: Implementar parsing de salary_text para extraer valores numéricos
    
    # incluye (AND entre atributos, OR entre valores)
    # Pero primero, verificar si tenemos tanto industry como area para manejarlos de forma especial
    has_industry = 'industry' in include
    has_area = 'area' in include
    
    for attr, values in include.items():
        if attr in field_mapping:
            mapped_field = field_mapping[attr]
            q = Q()
            print(f"\n   📌 Aplicando INCLUDE: {attr} = {values}")
            print(f"      Mapeo a campo: {mapped_field}")
            
            for v in values:
                if attr == 'role':
                    # Para role, buscar en el título
                    q |= Q(**{f"{mapped_field}__icontains": v})
                    print(f"      ⏺️  Condición: {mapped_field}__icontains='{v}'")
                elif attr == 'seniority':
                    # Para seniority, convertir a rango numérico de experiencia
                    experience_years = _seniority_to_experience_range(v)
                    if experience_years:
                        # Buscar empleos con esos años de experiencia
                        # Buscar tanto números solos como con "años" (singular y plural)
                        experience_q = Q()
                        for years in experience_years:
                            # Buscar el número solo
                            experience_q |= Q(**{f"{mapped_field}__icontains": str(years)})
                            # Buscar con "año" (singular)
                            experience_q |= Q(**{f"{mapped_field}__icontains": f"{years} año"})
                            # Buscar con "años" (plural)
                            experience_q |= Q(**{f"{mapped_field}__icontains": f"{years} años"})
                            # Para Junior (0-2), también buscar "junior", "jr", "entry", etc.
                            if years <= 2 and v.lower() in ['junior', 'jr']:
                                experience_q |= Q(**{f"{mapped_field}__icontains": "junior"})
                                experience_q |= Q(**{f"{mapped_field}__icontains": "jr"})
                                experience_q |= Q(**{f"{mapped_field}__icontains": "entry"})
                                experience_q |= Q(**{f"{mapped_field}__icontains": "trainee"})
                        q |= experience_q
                        print(f"      ⏺️  Condición: {mapped_field} contiene [{', '.join(map(str, experience_years))}] años o '{v}'")
                    else:
                        # Fallback: búsqueda por texto (junior, semi, senior)
                        q |= Q(**{f"{mapped_field}__icontains": v})
                        print(f"      ⏺️  Condición fallback: {mapped_field}__icontains='{v}'")
                elif attr == 'industry':
                    # Industry se busca en area - usar exact match primero, luego icontains como fallback
                    exact_q = Q(**{f"area__iexact": v})
                    contains_q = Q(**{f"area__icontains": v})
                    # Intentar exacto primero, pero también incluir contains para casos edge
                    combined_q = exact_q | contains_q
                    q |= combined_q
                    print(f"      ⏺️  Condición: area__iexact='{v}' O area__icontains='{v}'")
                elif attr == 'area':
                    # Para área funcional, buscar en subarea (NO en area, que es para industria)
                    # Usar exact match primero, luego contains como fallback
                    subarea_exact_q = Q(**{"subarea__iexact": v})
                    subarea_contains_q = Q(**{"subarea__icontains": v})
                    # Priorizar exact match, pero permitir contains como fallback
                    combined_q = subarea_exact_q | (subarea_contains_q & ~subarea_exact_q)
                    q |= combined_q
                    print(f"      ⏺️  Condición: subarea__iexact='{v}' O (subarea__icontains='{v}' sin exact)")
                elif attr == 'modality':
                    # Para modalidad, usar búsqueda insensible a mayúsculas
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
                elif attr == 'location':
                    # Para ubicación, usar palabras clave individuales porque puede haber variaciones
                    # (ej: "Santiago, RM" vs "Santiago, Región Metropolitana" vs "Santiago de Chile")
                    # También excluir ubicaciones inválidas (mensajes de error)
                    invalid_locations = ["necesitamos tu autorización", "autorización", "configuración", "privacidad", "navegador"]
                    location_lower = str(v).lower()
                    
                    # Si la ubicación buscada contiene palabras inválidas, no filtrar por ubicación
                    if any(invalid in location_lower for invalid in invalid_locations):
                        print(f"      ⚠️  Ubicación parece inválida, omitiendo filtro: '{v}'")
                    else:
                        # Verificar si hay filtro de modalidad remota - si es remoto, la ubicación es menos importante
                        is_remote = 'modality' in include and any('remoto' in str(m).lower() for m in include.get('modality', []))
                        
                        # Extraer palabras clave relevantes (excluir palabras comunes y signos de puntuación)
                        import re
                        # Remover signos de puntuación y dividir
                        location_clean = re.sub(r'[,\-\.;:]', ' ', location_lower)
                        common_words = ["de", "la", "el", "y", "región", "region", "comuna", "provincia", "del", "las", "los"]
                        keywords = [word.strip() for word in location_clean.split() 
                                   if word.strip() not in common_words and len(word.strip()) > 2]
                        
                        if keywords:
                            location_q = Q()
                            # Primero intentar con todas las palabras (más específico)
                            all_keywords_q = Q()
                            for keyword in keywords:
                                all_keywords_q &= Q(**{f"{mapped_field}__icontains": keyword})
                            
                            # Excluir ubicaciones inválidas
                            invalid_q = Q()
                            for invalid in invalid_locations:
                                invalid_q |= Q(**{f"{mapped_field}__icontains": invalid})
                            
                            # Si es remoto, también incluir empleos con ubicación inválida (son remotos de todos modos)
                            if is_remote:
                                # Para remoto: buscar que tenga la ubicación O que tenga ubicación inválida
                                location_q = all_keywords_q | invalid_q
                                print(f"      ⏺️  Condición (REMOTO): {mapped_field} contiene todas las palabras clave {keywords} O ubicación inválida")
                            else:
                                # Para presencial/híbrido: solo buscar ubicación válida que contenga las palabras clave
                                location_q = all_keywords_q & ~invalid_q
                                print(f"      ⏺️  Condición (PRESENCIAL/HÍBRIDO): {mapped_field} contiene todas las palabras clave {keywords} Y no es inválida")
                            
                            q |= location_q
                        else:
                            # Si no hay palabras clave, buscar la cadena completa
                            q |= Q(**{f"{mapped_field}__icontains": v})
                            print(f"      ⏺️  Condición: {mapped_field}__icontains='{v}'")
                elif attr in ['accessibility', 'transport']:
                    # Para accesibilidad y transporte, usar búsqueda booleana
                    if v is True:
                        q |= Q(**{mapped_field: True})
                        print(f"      ⏺️  Condición: {mapped_field}=True")
                    else:
                        q |= Q(**{mapped_field: False})
                        print(f"      ⏺️  Condición: {mapped_field}=False")
                else:
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
            
            qs_before = qs.count()
            qs = qs.filter(q)
            qs_after = qs.count()
            print(f"      📊 Después de filtrar: {qs_before} → {qs_after} empleos")
        else:
            print(f"   ⚠️  Campo no mapeado: {attr}")
    
    # excluye
    for attr, values in exclude.items():
        if attr in field_mapping:
            mapped_field = field_mapping[attr]
            q = Q()
            print(f"\n   🚫 Aplicando EXCLUDE: {attr} = {values}")
            print(f"      Mapeo a campo: {mapped_field}")
            
            for v in values:
                if attr == 'role':
                    q |= Q(**{f"{mapped_field}__icontains": v})
                    print(f"      ⏺️  Condición: {mapped_field}__icontains='{v}'")
                elif attr == 'seniority':
                    # Para seniority, convertir a rango numérico de experiencia
                    experience_years = _seniority_to_experience_range(v)
                    if experience_years:
                        # Excluir empleos con esos años de experiencia
                        experience_q = Q()
                        for years in experience_years:
                            experience_q |= Q(**{f"{mapped_field}__icontains": str(years)})
                        q |= experience_q
                        print(f"      ⏺️  Condición: {mapped_field} en [{', '.join(map(str, experience_years))}] años")
                    else:
                        # Fallback: búsqueda por texto
                        q |= Q(**{f"{mapped_field}__icontains": v})
                        print(f"      ⏺️  Condición fallback: {mapped_field}__icontains='{v}'")
                elif attr == 'industry':
                    # Industry se busca en area - usar exact match primero, luego icontains como fallback
                    exact_q = Q(**{f"area__iexact": v})
                    contains_q = Q(**{f"area__icontains": v})
                    # Intentar exacto primero, pero también incluir contains para casos edge
                    combined_q = exact_q | contains_q
                    q |= combined_q
                    print(f"      ⏺️  Condición: area__iexact='{v}' O area__icontains='{v}'")
                elif attr == 'area':
                    # Para área funcional, buscar en subarea (NO en area, que es para industria)
                    # Usar exact match primero, luego contains como fallback
                    subarea_exact_q = Q(**{"subarea__iexact": v})
                    subarea_contains_q = Q(**{"subarea__icontains": v})
                    # Priorizar exact match, pero permitir contains como fallback
                    combined_q = subarea_exact_q | (subarea_contains_q & ~subarea_exact_q)
                    q |= combined_q
                    print(f"      ⏺️  Condición: subarea__iexact='{v}' O (subarea__icontains='{v}' sin exact)")
                elif attr == 'modality':
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
                elif attr == 'location':
                    # Para ubicación en EXCLUDE, usar palabras clave individuales
                    invalid_locations = ["necesitamos tu autorización", "autorización", "configuración", "privacidad", "navegador"]
                    location_lower = str(v).lower()
                    if any(invalid in location_lower for invalid in invalid_locations):
                        print(f"      ⚠️  Ubicación parece inválida, omitiendo filtro: '{v}'")
                    else:
                        # Extraer palabras clave relevantes (excluir palabras comunes y signos de puntuación)
                        import re
                        # Remover signos de puntuación y dividir
                        location_clean = re.sub(r'[,\-\.;:]', ' ', location_lower)
                        common_words = ["de", "la", "el", "y", "región", "region", "comuna", "provincia", "del", "las", "los"]
                        keywords = [word.strip() for word in location_clean.split() 
                                   if word.strip() not in common_words and len(word.strip()) > 2]
                        
                        if keywords:
                            # Excluir si contiene TODAS las palabras clave
                            location_q = Q()
                            for keyword in keywords:
                                location_q &= Q(**{f"{mapped_field}__icontains": keyword})
                            q |= location_q
                            print(f"      ⏺️  Condición EXCLUDE: {mapped_field} contiene todas las palabras clave: {keywords}")
                        else:
                            q |= Q(**{f"{mapped_field}__icontains": v})
                            print(f"      ⏺️  Condición EXCLUDE: {mapped_field}__icontains='{v}'")
                elif attr in ['accessibility', 'transport']:
                    # Para accesibilidad y transporte, usar búsqueda booleana
                    if v is True:
                        q |= Q(**{mapped_field: True})
                        print(f"      ⏺️  Condición: {mapped_field}=True")
                    else:
                        q |= Q(**{mapped_field: False})
                        print(f"      ⏺️  Condición: {mapped_field}=False")
                else:
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
            
            qs_before = qs.count()
            qs = qs.exclude(q)
            qs_after = qs.count()
            print(f"      📊 Después de excluir: {qs_before} → {qs_after} empleos")
        else:
            print(f"   ⚠️  Campo no mapeado: {attr}")
    
    final_count = qs.count()
    print(f"\n   ✅ Resultado final de _APPLY: {final_count} empleos")
    return qs

def decide_jobs(include:dict, exclude:dict, salary_min:int|None, currency:str|None, topn:int=3, offset:int=0, variety:bool=False):
    """
    Intenta con reglas completas → si no hay resultados, RELAJA solo filtros menos críticos.
    NO relaja industry o area si eso haría que los resultados sean irrelevantes.
    
    Args:
        include: Filtros de inclusión
        exclude: Filtros de exclusión
        salary_min: Salario mínimo
        currency: Moneda
        topn: Número de resultados a devolver
        offset: Desplazamiento para paginación
        variety: Si True, intenta maximizar la variedad de resultados
    
    Returns:
        (results, steps, metadata) donde metadata contiene:
        - has_relevant_results: bool - Si los resultados son relevantes a los filtros originales
        - relaxed_filters: list - Lista de filtros que se relajaron
        - original_filters: dict - Filtros originales
    """
    print("\n" + "="*80)
    print("🔍 DECIDE_JOBS - Iniciando búsqueda de empleos")
    print("="*80)
    print(f"📥 INPUT:")
    print(f"   - include: {include}")
    print(f"   - exclude: {exclude}")
    print(f"   - salary_min: {salary_min}, currency: {currency}")
    print(f"   - topn: {topn}, offset: {offset}, variety: {variety}")
    
    # Guardar filtros originales para verificar relevancia
    original_include = {k: list(v) for k, v in include.items()}
    original_exclude = {k: list(v) for k, v in exclude.items()}
    
    steps = []
    base = JobPosting.objects.select_related('company', 'location').all()
    total_base = base.count()
    print(f"📊 Base total de empleos: {total_base}")

    # 1) intento estricto
    qs = _apply(base, include, exclude, salary_min, currency)
    strict_count = qs.count()
    steps.append(("apply", {"include":include, "exclude":exclude, "results": strict_count}))
    print(f"\n✅ INTENTO ESTRICTO:")
    print(f"   - Resultados encontrados: {strict_count}")
    
    if qs.exists():
        results = _get_varied_results(qs, topn, offset, variety)
        print(f"   - Resultados finales devueltos: {len(results)}")
        print("="*80)
        metadata = {
            "has_relevant_results": True,
            "relaxed_filters": [],
            "original_filters": {"include": original_include, "exclude": original_exclude}
        }
        return results, steps, metadata

    # Filtros críticos que NO deben relajarse si significan que los resultados serán irrelevantes
    # (industry y area son esenciales para mantener relevancia)
    critical_filters = ["industry", "area"]
    
    # Orden de relajación: primero filtros menos críticos
    # Prioridad: transport, accessibility, location, seniority, modality, luego industry/area solo como último recurso
    relax_priority = {
        "transport": 1,
        "accessibility": 1,
        "location": 2,
        "seniority": 3,
        "modality": 4,
        "role": 5,
        "industry": 6,  # Crítico - solo relajar si es absolutamente necesario
        "area": 7,      # Crítico - solo relajar si es absolutamente necesario
    }
    
    relax_order: List[Tuple[str, str, int]] = []
    for k in exclude.keys():
        priority = relax_priority.get(k, 9)
        relax_order.append(("exclude", k, priority))
    for k in include.keys():
        priority = relax_priority.get(k, 9)
        relax_order.append(("include", k, priority))
    
    # Ordenar por prioridad (menor número = menos crítico = relajar primero)
    relax_order.sort(key=lambda x: x[2])
    relax_order = [(kind, field) for kind, field, _ in relax_order]

    inc_cur = {k:list(v) for k,v in include.items()}
    exc_cur = {k:list(v) for k,v in exclude.items()}
    relaxed_filters = []

    print(f"\n⚠️  INTENTO ESTRICTO FALLÓ - Iniciando relajación de filtros")
    print(f"   - Orden de relajación (prioridad): {[(f, relax_priority.get(f, 9)) for _, f in relax_order]}")

    # Intentar relajar solo filtros menos críticos primero
    # Si tenemos industry o area, intentar mantenerlos siempre
    has_industry_or_area = "industry" in inc_cur or "area" in inc_cur
    
    for kind, field in relax_order:
        # Si es un filtro crítico (industry/area) y aún no hemos encontrado nada,
        # primero intentar sin relajar filtros críticos
        if field in critical_filters and has_industry_or_area:
            # Intentar relajar todos los demás filtros primero antes de tocar los críticos
            non_critical_relaxed = [f for f in relaxed_filters if f not in critical_filters]
            if len(non_critical_relaxed) < len([f for _, f in relax_order if f not in critical_filters]):
                print(f"   ⏭️  Saltando filtro crítico '{field}' - intentando otros filtros primero")
                continue
        
        if kind == "exclude" and field in exc_cur:
            exc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("exclude", field)}))
            relaxed_filters.append(field)
            print(f"\n🔄 Relajando: removiendo exclude.{field}")
        elif kind == "include" and field in inc_cur:
            inc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("include", field)}))
            relaxed_filters.append(field)
            print(f"\n🔄 Relajando: removiendo include.{field}")
        else:
            continue

        qs = _apply(base, inc_cur, exc_cur, salary_min, currency)
        relaxed_count = qs.count()
        steps.append(("apply", {"include":inc_cur, "exclude":exc_cur, "results": relaxed_count}))
        print(f"   - Resultados encontrados: {relaxed_count}")
        
        if qs.exists():
            results = _get_varied_results(qs, topn, offset, variety)
            
            # Verificar si los resultados son relevantes (tienen industry/area si los pedimos originalmente)
            is_relevant = True
            if original_include.get("industry") or original_include.get("area"):
                # Verificar que al menos algunos resultados tengan la industry/area original
                if "industry" not in inc_cur and original_include.get("industry"):
                    # Verificar si los resultados tienen la industry solicitada
                    matching_industry = sum(1 for r in results if r.get("area") in original_include.get("industry", []))
                    if matching_industry == 0:
                        is_relevant = False
                        print(f"   ⚠️  Resultados NO son relevantes: ninguno tiene industry original")
                
                if "area" not in inc_cur and original_include.get("area"):
                    # Verificar si los resultados tienen la subarea solicitada
                    matching_area = sum(1 for r in results if r.get("subarea") in original_include.get("area", []))
                    if matching_area == 0:
                        is_relevant = False
                        print(f"   ⚠️  Resultados NO son relevantes: ninguno tiene area funcional original")
            
            if not is_relevant:
                # Si los resultados no son relevantes, NO devolverlos
                print(f"   ❌ Resultados no son relevantes a los filtros originales, no devolverlos")
                continue
            
            print(f"   - Resultados finales devueltos: {len(results)}")
            print(f"   - Filtros relajados: {relaxed_filters}")
            print("="*80)
            metadata = {
                "has_relevant_results": True,
                "relaxed_filters": relaxed_filters,
                "original_filters": {"include": original_include, "exclude": original_exclude}
            }
            return results, steps, metadata

    # Si llegamos aquí, no hay resultados relevantes
    steps.append(("no_results", {"reason": "no relevant matches found after relaxing filters"}))
    print(f"\n❌ NO SE ENCONTRARON RESULTADOS RELEVANTES")
    print(f"   - Filtros originales: {original_include}")
    print(f"   - Filtros relajados intentados: {relaxed_filters}")
    print("="*80)
    metadata = {
        "has_relevant_results": False,
        "relaxed_filters": relaxed_filters,
        "original_filters": {"include": original_include, "exclude": original_exclude}
    }
    return [], steps, metadata

def _get_varied_results(queryset, topn: int, offset: int, variety: bool = False):
    """
    Obtiene resultados con variedad si se solicita, o resultados normales con paginación.
    """
    total_count = queryset.count()
    print(f"\n🎯 _GET_VARIED_RESULTS:")
    print(f"   - Total disponible: {total_count}")
    print(f"   - Solicitado: topn={topn}, offset={offset}, variety={variety}")
    
    if total_count == 0:
        print(f"   - ⚠️  No hay resultados disponibles")
        return []
    
    if variety:
        # Para maximizar variedad, ordenamos por diferentes criterios y tomamos muestras
        # Esto ayuda a evitar mostrar siempre los mismos empleos
        import random
        
        # Obtener una muestra más grande para seleccionar variedad
        sample_size = min(total_count, topn * 10)  # Obtener 10x más para seleccionar variedad
        
        # Diferentes ordenamientos para variedad
        orderings = [
            ['-published_date', 'title'],  # Por fecha y título
            ['company__name', 'title'],    # Por empresa y título
            ['title', '-published_date'],  # Por título y fecha
            ['-id', 'title'],              # Por ID (aleatorio efectivo)
            ['location__raw_text', 'title'], # Por ubicación y título
        ]
        
        # Seleccionar ordenamiento aleatorio
        ordering = random.choice(orderings)
        print(f"   - 🌈 Modo VARIEDAD activado:")
        print(f"      Ordenamiento: {ordering}")
        print(f"      Muestra: {sample_size} empleos")
        
        varied_qs = queryset.order_by(*ordering)[:sample_size]
        
        # Convertir objetos a diccionarios para mantener relaciones
        varied_results = []
        for job in varied_qs:
            # Convertir rating de Decimal a float si existe
            rating = float(job.company.rating) if job.company.rating is not None else None
            job_dict = {
                'id': job.id,
                'title': job.title,
                'company': {'name': job.company.name, 'verified': job.company.verified, 'rating': rating},
                'location': {'raw_text': job.location.raw_text if job.location else None},
                'area': job.area,
                'subarea': job.subarea,
                'work_modality': job.work_modality,
                'contract_type': job.contract_type,
                'workday': job.workday,
                'salary_text': job.salary_text,
                'min_experience': job.min_experience,
                'min_education': job.min_education,
                'published_date': job.published_date,
                'accessibility_mentioned': job.accessibility_mentioned,
                'transport_mentioned': job.transport_mentioned,
                'disability_friendly': job.disability_friendly,
                'url': job.url,
            }
            varied_results.append(job_dict)
        
        random.shuffle(varied_results)
        
        # Aplicar offset y limit
        start_idx = offset
        end_idx = start_idx + topn
        print(f"      Offset aplicado: {start_idx} → {end_idx}")
        
        # Si no hay suficientes resultados con variedad, usar paginación normal
        if start_idx >= len(varied_results):
            # Fallback a paginación normal
            print(f"      ⚠️  Offset demasiado alto, usando fallback normal")
            ordered_qs = queryset.order_by('id')
            fallback_results = []
            for job in ordered_qs[offset:offset + topn]:
                rating = float(job.company.rating) if job.company.rating is not None else None
                job_dict = {
                    'id': job.id,
                    'title': job.title,
                    'company': {'name': job.company.name, 'verified': job.company.verified, 'rating': rating},
                    'location': {'raw_text': job.location.raw_text if job.location else None},
                    'area': job.area,
                    'subarea': job.subarea,
                    'work_modality': job.work_modality,
                    'contract_type': job.contract_type,
                    'workday': job.workday,
                    'salary_text': job.salary_text,
                    'min_experience': job.min_experience,
                    'min_education': job.min_education,
                    'published_date': job.published_date,
                    'accessibility_mentioned': job.accessibility_mentioned,
                    'transport_mentioned': job.transport_mentioned,
                    'disability_friendly': job.disability_friendly,
                    'url': job.url,
                }
                fallback_results.append(job_dict)
            if fallback_results:
                print(f"      📦 Resultados fallback: {len(fallback_results)}")
                return fallback_results
            else:
                # Si aún no hay resultados, relajar filtros
                print(f"      ⚠️  Sin resultados, mostrando primeros {topn}")
                fallback_list = []
                for job in queryset.order_by('id')[:topn]:
                    rating = float(job.company.rating) if job.company.rating is not None else None
                    job_dict = {
                        'id': job.id,
                        'title': job.title,
                        'company': {'name': job.company.name, 'verified': job.company.verified, 'rating': rating},
                        'location': {'raw_text': job.location.raw_text if job.location else None},
                        'area': job.area,
                        'subarea': job.subarea,
                        'work_modality': job.work_modality,
                        'contract_type': job.contract_type,
                        'workday': job.workday,
                        'salary_text': job.salary_text,
                        'min_experience': job.min_experience,
                        'min_education': job.min_education,
                        'published_date': job.published_date,
                        'accessibility_mentioned': job.accessibility_mentioned,
                        'transport_mentioned': job.transport_mentioned,
                        'disability_friendly': job.disability_friendly,
                        'url': job.url,
                    }
                    fallback_list.append(job_dict)
                return fallback_list
        
        result = varied_results[start_idx:end_idx]
        print(f"      ✅ Resultados finales con variedad: {len(result)}")
        return result
    else:
        # Paginación normal con offset - usar ordenamiento consistente
        # Ordenar por ID para tener un orden predecible
        print(f"   - 📄 Modo PAGINACIÓN NORMAL:")
        print(f"      Ordenamiento: por ID")
        ordered_qs = queryset.order_by('id')
        result = []
        for job in ordered_qs[offset:offset + topn]:
            rating = float(job.company.rating) if job.company.rating is not None else None
            job_dict = {
                'id': job.id,
                'title': job.title,
                'company': {'name': job.company.name, 'verified': job.company.verified, 'rating': rating},
                'location': {'raw_text': job.location.raw_text if job.location else None},
                'area': job.area,
                'subarea': job.subarea,
                'work_modality': job.work_modality,
                'contract_type': job.contract_type,
                'workday': job.workday,
                'salary_text': job.salary_text,
                'min_experience': job.min_experience,
                'min_education': job.min_education,
                'published_date': job.published_date,
                'accessibility_mentioned': job.accessibility_mentioned,
                'transport_mentioned': job.transport_mentioned,
                'disability_friendly': job.disability_friendly,
                'url': job.url,
            }
            result.append(job_dict)
        print(f"      ✅ Resultados: {len(result)} (índices {offset} a {offset+topn})")
        return result

def get_job_pagination_info(include: dict, exclude: dict, salary_min: int = None, currency: str = None):
    """
    Obtiene información de paginación para los filtros dados.
    """
    base = JobPosting.objects.select_related('company', 'location').all()
    qs = _apply(base, include, exclude, salary_min, currency)
    
    total_count = qs.count()
    return {
        "total_jobs": total_count,
        "has_more": total_count > 3,  # Asumiendo que mostramos 3 por defecto
        "estimated_pages": (total_count + 2) // 3  # Páginas de 3 empleos
    }

def analyze_available_alternatives(original_include: dict, exclude: dict = None):
    """
    Analiza qué alternativas tienen empleos disponibles relajando filtros específicos.
    Devuelve sugerencias de qué slots cambiar para encontrar empleos.
    
    Returns:
        dict con:
        - alternatives: lista de alternativas con empleos disponibles
        - suggestions: mensajes de sugerencia para el usuario
    """
    if exclude is None:
        exclude = {}
    
    base = JobPosting.objects.select_related('company', 'location').all()
    alternatives = []
    suggestions = []
    
    # Prioridad de filtros a relajar (menos críticos primero)
    filter_priority = ["transport", "accessibility", "location", "seniority", "modality", "role", "industry", "area"]
    
    # Obtener datos disponibles en BD para sugerencias
    from .nlp import get_current_industries, get_current_areas, get_current_modalities
    
    available_industries = get_current_industries()
    available_areas = get_current_areas()
    available_modalities = get_current_modalities()
    
    # 1. Intentar relajar filtros uno por uno manteniendo los críticos
    critical_filters = ["industry", "area"]
    has_critical = any(f in original_include for f in critical_filters)
    
    for filter_name in filter_priority:
        if filter_name not in original_include:
            continue
        
        # Crear copia de filtros sin este filtro
        test_include = {k: list(v) for k, v in original_include.items() if k != filter_name}
        
        # Solo sugerir alternativas si mantenemos filtros críticos
        if has_critical:
            critical_preserved = any(f in test_include for f in critical_filters)
            if not critical_preserved:
                continue  # No sugerir si perdemos todos los filtros críticos
        
        qs = _apply(base, test_include, exclude, None, None)
        count = qs.count()
        
        if count > 0:
            # Verificar que los resultados sean relevantes
            results = _get_varied_results(qs, topn=3, offset=0, variety=False)
            if results:
                # Verificar relevancia (si había industry/area original, verificar que los resultados los tengan)
                is_relevant = True
                if original_include.get("industry"):
                    matching = sum(1 for r in results if r.get("area") in original_include.get("industry", []))
                    if matching == 0 and filter_name == "industry":
                        is_relevant = False
                
                if original_include.get("area"):
                    matching = sum(1 for r in results if r.get("subarea") in original_include.get("area", []))
                    if matching == 0 and filter_name == "area":
                        is_relevant = False
                
                if is_relevant:
                    filter_label = {
                        "industry": "industria",
                        "area": "área funcional",
                        "modality": "modalidad",
                        "seniority": "experiencia",
                        "location": "ubicación",
                        "transport": "transporte",
                        "accessibility": "accesibilidad"
                    }.get(filter_name, filter_name)
                    
                    alternatives.append({
                        "filter_to_remove": filter_name,
                        "filter_label": filter_label,
                        "jobs_available": count,
                        "keep_filters": test_include
                    })
    
    # 2. Generar sugerencias basadas en alternativas encontradas
    if alternatives:
        suggestions.append("💡 **Te puedo ayudar a encontrar empleos si:**")
        
        # Ordenar por número de empleos disponibles (más primero)
        alternatives.sort(key=lambda x: x["jobs_available"], reverse=True)
        
        for alt in alternatives[:3]:  # Mostrar hasta 3 alternativas
            jobs_count = alt["jobs_available"]
            filter_label = alt["filter_label"]
            suggestions.append(f"• **Quitas el filtro de {filter_label}**: Encontraría {jobs_count} empleos")
        
        # Sugerir cambiar valores específicos basados en qué tiene más empleos disponibles
        # Probar cada valor alternativo y sugerir los que tienen más empleos
        if "industry" in original_include:
            # Probar otras industrias
            current_industry = original_include["industry"][0] if original_include["industry"] else None
            other_include = {k: list(v) for k, v in original_include.items()}
            industry_suggestions = []
            
            for other_ind in available_industries:
                if other_ind == current_industry:
                    continue
                other_include["industry"] = [other_ind]
                test_qs = _apply(base, other_include, exclude, None, None)
                count = test_qs.count()
                if count > 0:
                    industry_suggestions.append((other_ind, count))
            
            # Ordenar por número de empleos (más primero) y tomar las top 2
            industry_suggestions.sort(key=lambda x: x[1], reverse=True)
            if industry_suggestions:
                top_industries = [ind for ind, _ in industry_suggestions[:2]]
                suggestions.append(f"• **Cambia la industria** a: {', '.join(top_industries)}")
        
        if "area" in original_include:
            # Probar otras áreas funcionales
            current_area = original_include["area"][0] if original_include["area"] else None
            other_include = {k: list(v) for k, v in original_include.items()}
            area_suggestions = []
            
            for other_area in available_areas[:10]:  # Limitar a las primeras 10 para no hacer demasiadas consultas
                if other_area == current_area:
                    continue
                other_include["area"] = [other_area]
                test_qs = _apply(base, other_include, exclude, None, None)
                count = test_qs.count()
                if count > 0:
                    area_suggestions.append((other_area, count))
            
            # Ordenar por número de empleos (más primero) y tomar las top 2
            area_suggestions.sort(key=lambda x: x[1], reverse=True)
            if area_suggestions:
                top_areas = [area for area, _ in area_suggestions[:2]]
                suggestions.append(f"• **Cambia el área funcional** a: {', '.join(top_areas)}")
        
        if "modality" in original_include:
            # Probar otras modalidades
            current_modality = original_include["modality"][0] if original_include["modality"] else None
            other_modalities = [mod for mod in available_modalities if mod != current_modality]
            if other_modalities:
                suggestions.append(f"• **Cambia la modalidad** a: {', '.join(other_modalities)}")
        
        if "location" in original_include:
            suggestions.append("• **Quita o cambia la ubicación** para ver más opciones")
        
        if "seniority" in original_include:
            suggestions.append("• **Quita o cambia el nivel de experiencia** para ver más opciones")
    
    # 3. Si no hay alternativas, sugerir cambiar valores críticos con opciones específicas
    if not alternatives and has_critical:
        if "industry" in original_include:
            # Probar otras industrias para sugerir específicamente
            current_industry = original_include["industry"][0] if original_include["industry"] else None
            other_include = {k: list(v) for k, v in original_include.items() if k != "industry"}
            industry_suggestions = []
            
            for other_ind in available_industries:
                if other_ind == current_industry:
                    continue
                other_include["industry"] = [other_ind]
                test_qs = _apply(base, other_include, exclude, None, None)
                count = test_qs.count()
                if count > 0:
                    industry_suggestions.append((other_ind, count))
            
            if industry_suggestions:
                industry_suggestions.sort(key=lambda x: x[1], reverse=True)
                top_industries = [ind for ind, _ in industry_suggestions[:2]]
                suggestions.append(f"💡 **Cambia la industria** a: {', '.join(top_industries)} (hay {industry_suggestions[0][1]} empleos disponibles)")
            else:
                suggestions.append(f"💡 **Cambia la industria** a otra opción disponible (Tecnología, Salud, etc.)")
        
        if "area" in original_include:
            # Probar otras áreas funcionales
            current_area = original_include["area"][0] if original_include["area"] else None
            other_include = {k: list(v) for k, v in original_include.items() if k != "area"}
            area_suggestions = []
            
            for other_area in available_areas[:10]:  # Limitar consultas
                if other_area == current_area:
                    continue
                other_include["area"] = [other_area]
                test_qs = _apply(base, other_include, exclude, None, None)
                count = test_qs.count()
                if count > 0:
                    area_suggestions.append((other_area, count))
            
            if area_suggestions:
                area_suggestions.sort(key=lambda x: x[1], reverse=True)
                top_areas = [area for area, _ in area_suggestions[:2]]
                suggestions.append(f"💡 **Cambia el área funcional** a: {', '.join(top_areas)} (hay {area_suggestions[0][1]} empleos disponibles)")
            else:
                suggestions.append(f"💡 **Cambia el área funcional** a otra opción disponible")
        
        if "modality" in original_include:
            other_modalities = [mod for mod in available_modalities if mod not in original_include.get("modality", [])]
            if other_modalities:
                suggestions.append(f"💡 **Cambia la modalidad** a: {', '.join(other_modalities)}")
    
    return {
        "alternatives": alternatives,
        "suggestions": suggestions
    }