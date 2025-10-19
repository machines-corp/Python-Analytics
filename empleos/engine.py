from typing import Tuple, List, Dict
from .models import JobPosting
from django.db.models import Q

def _apply(queryset, include:dict, exclude:dict, salary_min:int|None, currency:str|None):
    qs = queryset
    
    # Mapeo de campos del modelo Job a JobPosting
    field_mapping = {
        'industry': 'area',  # Por ahora usar area como proxy para industry
        'area': 'area',
        'role': 'title',  # Mapear role a title
        'seniority': 'min_experience',  # Mapear seniority a min_experience
        'modality': 'work_modality',
        'location': 'location__raw_text',
        'currency': 'salary_text',  # Para salario usaremos salary_text
    }
    
    # salario - por ahora no aplicamos filtro de salario ya que JobPosting usa salary_text
    # TODO: Implementar parsing de salary_text para extraer valores numéricos
    
    # incluye (AND entre atributos, OR entre valores)
    for attr, values in include.items():
        if attr in field_mapping:
            mapped_field = field_mapping[attr]
            q = Q()
            for v in values:
                if attr == 'industry':
                    # Para industria, buscar en el área (proxy)
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'role':
                    # Para role, buscar en el título
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'seniority':
                    # Para seniority, buscar en min_experience
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'area':
                    # Para área, usar búsqueda parcial
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'modality':
                    # Para modalidad, usar búsqueda insensible a mayúsculas
                    q |= Q(**{f"{mapped_field}__iexact": v})
                else:
                    q |= Q(**{f"{mapped_field}__iexact": v})
            qs = qs.filter(q)
    
    # excluye
    for attr, values in exclude.items():
        if attr in field_mapping:
            mapped_field = field_mapping[attr]
            q = Q()
            for v in values:
                if attr == 'industry':
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'role':
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'seniority':
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'area':
                    q |= Q(**{f"{mapped_field}__icontains": v})
                elif attr == 'modality':
                    q |= Q(**{f"{mapped_field}__iexact": v})
                else:
                    q |= Q(**{f"{mapped_field}__iexact": v})
            qs = qs.exclude(q)
    
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
    steps = []
    base = JobPosting.objects.select_related('company', 'location').all()

    # 1) intento estricto
    qs = _apply(base, include, exclude, salary_min, currency)
    steps.append(("apply", {"include":include, "exclude":exclude, "results": qs.count()}))
    if qs.exists():
        results = _get_varied_results(qs, topn, offset, variety)
        return results, steps

    # orden de relajación por defecto
    relax_order: List[Tuple[str,str]] = []
    for k in exclude.keys(): relax_order.append(("exclude", k))
    for k in include.keys(): relax_order.append(("include", k))

    inc_cur = {k:list(v) for k,v in include.items()}
    exc_cur = {k:list(v) for k,v in exclude.items()}

    for kind, field in relax_order:
        if kind == "exclude" and field in exc_cur:
            exc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("exclude", field)}))
        elif kind == "include" and field in inc_cur:
            inc_cur.pop(field, None)
            steps.append(("relax", {"removed": ("include", field)}))
        else:
            continue

        qs = _apply(base, inc_cur, exc_cur, salary_min, currency)
        steps.append(("apply", {"include":inc_cur, "exclude":exc_cur, "results": qs.count()}))
        if qs.exists():
            results = _get_varied_results(qs, topn, offset, variety)
            return results, steps

    steps.append(("fallback", {"reason": "no matches even after relaxing"}))
    results = _get_varied_results(base, topn, offset, variety)
    return results, steps

def _get_varied_results(queryset, topn: int, offset: int, variety: bool = False):
    """
    Obtiene resultados con variedad si se solicita, o resultados normales con paginación.
    """
    total_count = queryset.count()
    if total_count == 0:
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
        varied_qs = queryset.order_by(*ordering)[:sample_size]
        
        # Convertir a lista y mezclar para mayor variedad
        varied_results = list(varied_qs.values())
        random.shuffle(varied_results)
        
        # Aplicar offset y limit
        start_idx = offset
        end_idx = start_idx + topn
        
        # Si no hay suficientes resultados con variedad, usar paginación normal
        if start_idx >= len(varied_results):
            # Fallback a paginación normal
            ordered_qs = queryset.order_by('id')
            fallback_results = list(ordered_qs[offset:offset + topn].values())
            if fallback_results:
                return fallback_results
            else:
                # Si aún no hay resultados, relajar filtros
                return list(queryset.order_by('id')[:topn].values())
        
        return varied_results[start_idx:end_idx]
    else:
        # Paginación normal con offset - usar ordenamiento consistente
        # Ordenar por ID para tener un orden predecible
        ordered_qs = queryset.order_by('id')
        return list(ordered_qs[offset:offset + topn].values())

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