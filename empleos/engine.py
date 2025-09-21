from typing import Tuple, List, Dict
from .models import Job
from django.db.models import Q

def _apply(queryset, include:dict, exclude:dict, salary_min:int|None, currency:str|None):
    qs = queryset
    # salario
    if salary_min is not None and currency:
        qs = qs.filter(currency=currency, salary_max__gte=salary_min)
    # incluye (AND entre atributos, OR entre valores)
    for attr, values in include.items():
        q = Q()
        for v in values:
            q |= Q(**{f"{attr}__iexact": v})
        qs = qs.filter(q)
    # excluye
    for attr, values in exclude.items():
        q = Q()
        for v in values:
            q |= Q(**{f"{attr}__iexact": v})
        qs = qs.exclude(q)
    return qs

def decide_jobs(include:dict, exclude:dict, salary_min:int|None, currency:str|None, topn:int=3):
    """
    Intenta con reglas completas → si no hay resultados, RELAJA:
    1) Quita exclusiones (en orden dado)
    2) Quita inclusiones (en orden dado)
    """
    steps = []
    base = Job.objects.all()

    # 1) intento estricto
    qs = _apply(base, include, exclude, salary_min, currency)
    steps.append(("apply", {"include":include, "exclude":exclude, "results": qs.count()}))
    if qs.exists():
        return list(qs[:topn].values()), steps

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
            return list(qs[:topn].values()), steps

    steps.append(("fallback", {"reason": "no matches even after relaxing"}))
    return list(base[:topn].values()), steps