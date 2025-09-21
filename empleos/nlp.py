import re
from typing import Dict, List, Tuple

SYNONYMS = {
    "remoto": ["remoto", "teletrabajo", "desde casa"],
    "híbrido": ["hibrido", "híbrido", "mixto"],
    "presencial": ["presencial", "en oficina"],
    "junior": ["jr", "junior", "entry"],
    "semi": ["semi", "ssr", "semi-senior", "semisenior"],
    "senior": ["sr", "senior", "experto"],
    "datos": ["datos", "data", "analítica", "analytics"],
    "desarrollo": ["desarrollo", "dev", "programación", "software"],
    "infraestructura": ["infraestructura", "devops", "ops"],
    "calidad": ["qa", "calidad", "testing"],
    "soporte": ["soporte", "helpdesk", "mesa de ayuda"],
    "diseño": ["ux", "ui", "diseño", "ux/ui"],
    "docencia": ["docencia", "profesor", "enseñanza"],

    "data analyst": ["analista de datos", "data analyst", "analista datos"],
    "data engineer": ["data engineer", "ingeniero de datos"],
    "backend developer": ["backend developer", "desarrollador backend"],
    "full stack dev": ["full stack", "fullstack", "desarrollador full stack"],
    "qa analyst": ["qa", "analista qa", "tester"],
    "devops engineer": ["devops", "devops engineer"],
    "ux/ui designer": ["ux/ui", "ux ui", "diseñador ux", "diseñador ui", "ux designer", "ui designer"],
}

INDUSTRIES = ["Tecnología","Educación","Salud","Finanzas"]
MODALITIES = ["Remoto","Híbrido","Presencial"]
SENIORITIES = ["Junior","Semi","Senior"]
AREAS = ["Datos","Desarrollo","Infraestructura","Calidad","Soporte","Diseño","Docencia","Gestión","Clínica","Apoyo","Análisis"]
LOCATIONS = ["Chile","LatAm"]  # extiende con comunas/ciudades según tu dataset

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

NEG_PATTERNS = [r"no\s+([a-z0-9\-/\s]+)", r"sin\s+([a-z0-9\-/\s]+)"]

def _negations(text: str) -> List[str]:
    neg = []
    for pat in NEG_PATTERNS:
        for m in re.finditer(pat, text):
            term = m.group(1).strip()
            term = re.split(r"\s+(y|o|ni|pero|,|\.)\s+", term)[0]
            neg.append(term)
    return neg

def parse_prompt(prompt: str, roles_from_db: List[str]) -> Tuple[dict, dict, int|None, str]:
    raw = _norm(prompt)
    # Moneda + salario
    currency = "USD" if ("usd" in raw or "$" in raw) else ("CLP" if ("clp" in raw or "pesos" in raw) else None)
    salary_min = None
    nums = re.findall(r"\d[\d\.]*", raw)
    if nums:
        try: salary_min = int(nums[0].replace(".",""))
        except: salary_min = None

    include, exclude = {}, {}

    # Modalidad
    for m in MODALITIES:
        if m.lower() in raw:
            include.setdefault("modality", []).append(m)
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["remoto","híbrido","presencial"]:
            include.setdefault("modality", []).append({"remoto":"Remoto","híbrido":"Híbrido","presencial":"Presencial"}[canon])

    # Seniority
    for s in SENIORITIES:
        if s.lower() in raw:
            include.setdefault("seniority", []).append(s)
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["junior","semi","senior"]:
            include.setdefault("seniority", []).append(canon.capitalize())

    # Industria
    for ind in INDUSTRIES:
        if ind.lower() in raw:
            include.setdefault("industry", []).append(ind)

    # Área
    for a in AREAS:
        if a.lower() in raw:
            include.setdefault("area", []).append(a)
    for syn, canon in INV_SYNS.items():
        if syn in raw and canon in ["datos","desarrollo","infraestructura","calidad","soporte","diseño","docencia"]:
            include.setdefault("area", []).append(canon.capitalize())

    # Role (con sinónimos + exact match)
    role_hits = []
    for r in roles_from_db:
        if _norm(r) in raw:
            role_hits.append(r)
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

    # Ubicación
    for loc in LOCATIONS:
        if loc.lower() in raw:
            include.setdefault("location", []).append(loc)

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