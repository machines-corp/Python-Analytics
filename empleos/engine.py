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
    field_mapping = {
        'industry': 'area',  # Industry se mapea a area (ej: "Tecnología" → area="Tecnología")
        'area': 'area',      # Area se mapea a area (ej: "Diseño" → area="Diseño")  
        'role': 'title',  # Mapear role a title
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
                    # Industry se busca en area
                    q |= Q(**{f"area__icontains": v})
                    print(f"      ⏺️  Condición: area__icontains='{v}'")
                elif attr == 'area':
                    # Para area, buscar en area Y subarea
                    area_q = Q(**{f"area__icontains": v})
                    # También buscar en subarea si está disponible
                    subarea_q = Q(**{"subarea__icontains": v})
                    combined_q = area_q | subarea_q
                    q |= combined_q
                    print(f"      ⏺️  Condición: area__icontains O subarea__icontains='{v}'")
                elif attr == 'modality':
                    # Para modalidad, usar búsqueda insensible a mayúsculas
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
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
                    # Industry se busca en area
                    q |= Q(**{f"area__icontains": v})
                    print(f"      ⏺️  Condición: area__icontains='{v}'")
                elif attr == 'area':
                    # Para area, buscar en area Y subarea
                    area_q = Q(**{f"area__icontains": v})
                    # También buscar en subarea si está disponible
                    subarea_q = Q(**{"subarea__icontains": v})
                    combined_q = area_q | subarea_q
                    q |= combined_q
                    print(f"      ⏺️  Condición: area__icontains O subarea__icontains='{v}'")
                elif attr == 'modality':
                    q |= Q(**{f"{mapped_field}__iexact": v})
                    print(f"      ⏺️  Condición: {mapped_field}__iexact='{v}'")
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
    Intenta con reglas completas → si no hay resultados, RELAJA:
    1) Quita exclusiones (en orden dado)
    2) Quita inclusiones (en orden dado)
    
    Args:
        include: Filtros de inclusión
        exclude: Filtros de exclusión
        salary_min: Salario mínimo
        currency: Moneda
        topn: Número de resultados a devolver
        offset: Desplazamiento para paginación
        variety: Si True, intenta maximizar la variedad de resultados
    """
    print("\n" + "="*80)
    print("🔍 DECIDE_JOBS - Iniciando búsqueda de empleos")
    print("="*80)
    print(f"📥 INPUT:")
    print(f"   - include: {include}")
    print(f"   - exclude: {exclude}")
    print(f"   - salary_min: {salary_min}, currency: {currency}")
    print(f"   - topn: {topn}, offset: {offset}, variety: {variety}")
    
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
        return results, steps

    # orden de relajación por defecto
    relax_order: List[Tuple[str,str]] = []
    for k in exclude.keys(): relax_order.append(("exclude", k))
    for k in include.keys(): relax_order.append(("include", k))

    inc_cur = {k:list(v) for k,v in include.items()}
    exc_cur = {k:list(v) for k,v in exclude.items()}

    print(f"\n⚠️  INTENTO ESTRICTO FALLÓ - Iniciando relajación de filtros")
    print(f"   - Orden de relajación: {relax_order}")

    for kind, field in relax_order:
        if kind == "exclude" and field in exc_cur:
            exc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("exclude", field)}))
            print(f"\n🔄 Relajando: removiendo exclude.{field}")
        elif kind == "include" and field in inc_cur:
            inc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("include", field)}))
            print(f"\n🔄 Relajando: removiendo include.{field}")
        else:
            continue

        qs = _apply(base, inc_cur, exc_cur, salary_min, currency)
        relaxed_count = qs.count()
        steps.append(("apply", {"include":inc_cur, "exclude":exc_cur, "results": relaxed_count}))
        print(f"   - Resultados encontrados: {relaxed_count}")
        
        if qs.exists():
            results = _get_varied_results(qs, topn, offset, variety)
            print(f"   - Resultados finales devueltos: {len(results)}")
            print("="*80)
            return results, steps

    steps.append(("fallback", {"reason": "no matches even after relaxing"}))
    print(f"\n❌ TODOS LOS INTENTOS FALLARON - Usando fallback sin filtros")
    results = _get_varied_results(base, topn, offset, variety)
    print(f"   - Resultados finales devueltos: {len(results)}")
    print("="*80)
    return results, steps

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