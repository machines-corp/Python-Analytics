# -*- coding: utf-8 -*-
"""
Laborum (CL) - Inclusivos (Apto discapacidad)
Listado y Detalle con Playwright (Chromium headless)
Salida: JSONL (+ CSV opcional)

Ejemplo:
  python empleos/scraping_2.py \
    --pages 2 \
    --out-json out/empleos_laborum_discapacidad.jsonl \
    --out-csv out/empleos_laborum_discapacidad.csv
"""

import os, re, json, time, random, argparse, hashlib, sys
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
import pandas as pd

BASE_URL = "https://www.laborum.cl"
LIST_URL = f"{BASE_URL}/empleos-discapacitados-apto.html?landing-empleos-inclusivos=true"
UA_FALLBACK = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"

KEYWORDS_INCLUSION = [
    "discapacidad", "inclusión", "inclusivo", "neurodiverg", "tea", "asperger",
    "movilidad reducida", "silla de ruedas", "acomodo razonable", "accesibilidad",
    "rampa", "ascensor", "baño accesible", "teletrabajo", "remoto", "home office",
    "apto discapacidad"
]
KEYWORDS_TRANSPORTE = [
    "transporte", "bus de acercamiento", "locomoción", "movilización",
    "estacionamiento", "estacionamientos", "bip", "subsidio transporte"
]

MESES_ES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12
}

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def slow(a: float, b: float):
    time.sleep(random.uniform(a, b))

def safe_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def normalizar_fecha_es(texto: str, hoy: Optional[date]=None) -> Optional[str]:
    if not texto:
        return None
    t = texto.strip().lower()
    hoy = hoy or date.today()

    if "hoy" in t:
        return hoy.isoformat()
    if "ayer" in t:
        return (hoy - timedelta(days=1)).isoformat()

    m = re.search(r"hace\s+(\d+)\s*d[ií]as?", t)
    if m:
        d = int(m.group(1))
        return (hoy - timedelta(days=d)).isoformat()

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
    if m:
        dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yyyy < 100: yyyy += 2000
        try:
            return date(yyyy, mm, dd).isoformat()
        except Exception:
            return None

    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?", t)
    if m:
        dd = int(m.group(1))
        mes_txt = m.group(2).translate(str.maketrans("áéíóú","aeiou"))
        mm = MESES_ES.get(mes_txt)
        yyyy = int(m.group(3)) if m.group(3) else hoy.year
        if mm:
            try:
                return date(yyyy, mm, dd).isoformat()
            except Exception:
                return None
    return None

def flags_accesibilidad_y_transporte(texto: str) -> Tuple[bool, bool, List[str], List[str]]:
    t = (texto or "").lower()
    acc_hits = [kw for kw in KEYWORDS_INCLUSION if kw in t]
    trans_hits = [kw for kw in KEYWORDS_TRANSPORTE if kw in t]
    return (len(acc_hits) > 0, len(trans_hits) > 0, acc_hits, trans_hits)

# ----------------- Playwright helpers -----------------

def launch_browser(pw, headless=True):
    return pw.chromium.launch(
        headless=headless,
        args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--disable-setuid-sandbox"]
    )

def get_text_first(page, selectors: List[str]) -> Optional[str]:
    for sel in selectors:
        try:
            node = page.locator(sel).first
            if node and node.count() > 0:
                txt = node.inner_text(timeout=1000)
                if txt:
                    return safe_text(txt)
        except Exception:
            continue
    return None

def element_exists(page, selector: str) -> bool:
    try:
        return page.locator(selector).first.count() > 0
    except Exception:
        return False

# ----------------- Listado -----------------

def collect_list_urls(pages: int, sleep_min: float, sleep_max: float) -> List[str]:
    urls, seen = [], set()
    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=True)
        ctx = browser.new_context(user_agent=UA_FALLBACK, locale="es-CL")
        page = ctx.new_page()
        log(f"[LIST] GOTO {LIST_URL}")
        page.goto(LIST_URL, timeout=90000, wait_until="domcontentloaded")

        # intenta esperar que el listado pinte al menos 1 tarjeta
        try:
            page.wait_for_selector('a[href^="/empleos/"][href$=".html"]', timeout=12000)
        except PwTimeout:
            log("[LIST] No hubo anclas en 12s; continuo con scrolls...")

        for i in range(pages):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            page.wait_for_timeout(2000)
            anchors = page.locator('a[href^="/empleos/"][href$=".html"]').all()
            found = 0
            for a in anchors:
                href = a.get_attribute("href") or ""
                if not href or href.startswith("#"):
                    continue
                full = href if href.startswith("http") else (BASE_URL + href)
                if full not in seen:
                    seen.add(full); urls.append(full); found += 1
            log(f"[LIST] step {i+1}/{pages} -> +{found} (total {len(urls)})")
            page.wait_for_timeout(random.randint(800,1400))

        browser.close()
    return urls

# ----------------- Detalle -----------------

def parse_detail_with_playwright(ctx, url: str) -> Optional[Dict]:
    """Navega al detalle y extrae campos ya renderizados."""
    page = ctx.new_page()
    try:
        page.goto(url, timeout=90000, wait_until="domcontentloaded")
        # esperar un poco para que hidrate (React)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # ---------- Título ----------
        titulo = get_text_first(page, [
            "h1",
            'h1[data-testid*="jobTitle"]',
            ".job-title h1",
            '[class*="title"] h1',
        ])

        # ---------- Empresa ----------
        empresa = get_text_first(page, [
            'a[href*="/empresa/"] h3',
            'a[href*="/empresa/"]',
            ".company-name h3",
            ".company-name",
            '[itemprop="hiringOrganization"]',
        ])

        # ---------- Ubicación ----------
        ubicacion = get_text_first(page, [
            'i[name="icon-light-location-pin"] + span h3',
            '[data-testid*="jobLocation"]',
            '.job-location',
            '[class*="location"] h3',
            '[class*="location"]',
            'li:has-text("Ubicación")',
        ])

        # ---------- Fecha publicación ----------
        fecha_raw = get_text_first(page, [
            'time[datetime]',
            'h3:has-text("Publicado")',
            'span[class*="date"]',
            '.posted-date',
            '.publication-date',
            'text=/Publicado|Publicada|hace\\s+\\d+\\s*d[ií]as/i'
        ])
        fecha_publicacion = normalizar_fecha_es(fecha_raw or "")

        # ---------- Modalidad / Apto / Múltiples ----------
        modalidad = None
        for m in ("Remoto","Híbrido","Hibrido","Presencial"):
            if page.get_by_text(m, exact=True).count() > 0:
                modalidad = m.lower(); break

        apto_discapacidad = element_exists(page, 'i[name="icon-light-discapacity"]') or page.get_by_text("Apto discapacidad", exact=False).count() > 0
        multiple_vacantes = page.get_by_text("Múltiples vacantes", exact=False).count() > 0

        # ---------- Rating / Verificada ----------
        rating_empresa = None
        try:
            rating_txt = get_text_first(page, [
                'i[name="icon-light-star"] ~ h3',
                'i[name="icon-icon-bold-star"] ~ h3',
                '[class*="star"] ~ h3',
                '.rating h3',
            ])
            if rating_txt:
                mrat = re.search(r"(\d+(?:[.,]\d+)?)", rating_txt)
                if mrat: rating_empresa = float(mrat.group(1).replace(",", "."))
        except Exception:
            pass

        empresa_verificada = element_exists(page, 'i[name="icon-bold-verified"]') or element_exists(page, ".company-verified")

        # ---------- Descripción ----------
        descripcion = get_text_first(page, [
            "[data-testid*='jobDescription']",
            ".job-description",
            "article",
            ".description",
            ".desc",
        ])

        # ---------- Jornada / Salario (heurístico por texto) ----------
        page_text = safe_text(page.content())
        jornada = "full-time" if re.search(r"(full[- ]?time|jornada completa)", page_text, re.I) else (
                  "part-time" if re.search(r"(part[- ]?time|media jornada)", page_text, re.I) else None)
        salario = None
        msal = re.search(r"(\$|\bCLP\b)\s?([\d.]+)(?:\s*-\s*(\$?)([\d.]+))?", page_text, re.I)
        if msal:
            salario = msal.group(0)

        # ---------- Flags accesibilidad / transporte ----------
        acc_ok, trans_ok, acc_hits, trans_hits = flags_accesibilidad_y_transporte(f"{titulo or ''} {descripcion or ''}")

        # ---------- ID oferta ----------
        mid = re.search(r"-([0-9]{6,})\.html$", url)
        id_oferta = mid.group(1) if mid else None

        row = {
            "fecha_publicacion": fecha_publicacion,
            "titulo": titulo or None,
            "empresa": empresa or None,
            "ubicacion": ubicacion or None,
            "fuente": "Laborum",
            "url": url,
            "accesibilidad_mencionada": acc_ok,
            "transporte_mencionado": trans_ok,
            "tags_accesibilidad": ";".join(acc_hits),
            "tags_transporte": ";".join(trans_hits),
            "modalidad_trabajo": modalidad,
            "apto_discapacidad": bool(apto_discapacidad),
            "multiple_vacantes": bool(multiple_vacantes),
            "rating_empresa": rating_empresa,
            "empresa_verificada": bool(empresa_verificada),
            "tipo_contrato": None,
            "jornada": jornada,
            "salario": salario,
            "area": None,
            "subarea": None,
            "experiencia_min": None,
            "educacion_min": None,
            "beneficios": [],
            "descripcion": descripcion or None,
            "id_oferta": id_oferta,
            "hash": hashlib.md5(url.encode("utf-8")).hexdigest(),
        }
        return row

    except Exception as e:
        log(f"[ERR] detalle {url}: {e}")
        return None
    finally:
        try:
            page.close()
        except Exception:
            pass

# ----------------- Export -----------------

def export_jsonl(rows: List[Dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"[OK] JSONL -> {path} ({len(rows)} filas)")

def export_csv(rows: List[Dict], path: str):
    cols = ["fecha_publicacion","titulo","empresa","ubicacion","fuente","url",
            "accesibilidad_mencionada","transporte_mencionado","tags_accesibilidad","tags_transporte",
            "modalidad_trabajo","apto_discapacidad","multiple_vacantes","rating_empresa",
            "empresa_verificada","tipo_contrato","jornada","salario","area","subarea",
            "experiencia_min","educacion_min","beneficios","descripcion","id_oferta","hash"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df[cols].to_csv(path, index=False, encoding="utf-8-sig")
    log(f"[OK] CSV -> {path}")

# ----------------- Main -----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=int(os.getenv("PAGES", "2")), help="ciclos de scroll del listado")
    ap.add_argument("--sleep-min", type=float, default=float(os.getenv("SLEEP_MIN", "1.0")))
    ap.add_argument("--sleep-max", type=float, default=float(os.getenv("SLEEP_MAX", "2.0")))
    ap.add_argument("--out-json", type=str, default=os.getenv("OUT_JSON", "out/empleos_laborum_discapacidad.jsonl"))
    ap.add_argument("--out-csv", type=str, default=os.getenv("OUT_CSV", "out/empleos_laborum_discapacidad.csv"))
    args = ap.parse_args()

    # 1) Recolectar URLs del listado
    urls = collect_list_urls(args.pages, args.sleep_min, args.sleep_max)
    if not urls:
        log("[RUN] No se encontraron URLs en el listado. Revisa si cambió el DOM.")
        sys.exit(1)
    log(f"[RUN] URLs descubiertas: {len(urls)}")

    # 2) Detalle con Playwright
    rows = []
    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=True)
        ctx = browser.new_context(user_agent=UA_FALLBACK, locale="es-CL")
        for i, u in enumerate(urls, 1):
            log(f"[{i}/{len(urls)}] {u}")
            row = parse_detail_with_playwright(ctx, u)
            if row:
                rows.append(row)
            slow(args.sleep_min, args.sleep_max)
        browser.close()

    if not rows:
        log("[RUN] No se pudo extraer detalle de ninguna URL.")
        sys.exit(2)

    # 3) Export
    export_jsonl(rows, args.out_json)
    export_csv(rows, args.out_csv)

if __name__ == "__main__":
    main()