import json
import base64
import re
import time
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from empleos.models import Source, Company, Location, JobPosting
from empleos.nlp import parse_prompt, _norm

# Configuración de la API del SNE
TOKEN_URL = "https://test.api.bne.cl/token"
JOBS_URL = "https://test.api.bne.cl/JobOfferingsService/v1/1.0.0/jobofferings/active"
USERNAME = "e9b75m_XYbA5n0Dz33M_rbChsRMa"
PASSWORD = "bbctfOeNTfCyfhNa_xOl5kafYvMa"
SOURCE_NAME = "Servicio Nacional de Empleo (BNE)"


def get_or_create(model, **kwargs):
    """Helper para obtener o crear objetos"""
    obj, created = model.objects.get_or_create(**kwargs)
    return obj, created


def get_access_token(timeout=60):
    """
    Obtiene el token de acceso del API del SNE usando autenticación básica.
    """
    print("=" * 80)
    print("🔐 Obteniendo token de autenticación...")
    print("=" * 80)
    
    # Crear credenciales de autenticación básica
    credentials = f"{USERNAME}:{PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Body con grant_type
    data = {
        "grant_type": "client_credentials"
    }
    
    try:
        print(f"   ⏳ Enviando petición a {TOKEN_URL}...")
        response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=timeout)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        print(f"✅ Token obtenido exitosamente")
        print(f"   - Token type: {token_data.get('token_type')}")
        print(f"   - Expires in: {token_data.get('expires_in')} segundos")
        print(f"   - Scope: {token_data.get('scope')}")
        print(f"   - Access token: {access_token[:20]}...")
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   - Status code: {e.response.status_code}")
            print(f"   - Response: {e.response.text}")
        raise


def fetch_job_offerings(access_token, limit=100, offset=0, timeout=60):
    """
    Obtiene las ofertas de empleo del API del SNE.
    """
    print("=" * 80)
    print(f"📥 Obteniendo ofertas de empleo (limit={limit}, offset={offset})...")
    print(f"   ⏱️  Timeout configurado: {timeout} segundos")
    print("=" * 80)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "limit": limit,
        "offset": offset
    }
    
    try:
        print(f"   ⏳ Enviando petición a {JOBS_URL}...")
        print(f"   ⏳ Esto puede tardar entre 16-20 segundos, por favor espera...")
        start_time = time.time()
        
        response = requests.get(JOBS_URL, headers=headers, params=params, timeout=timeout)
        elapsed_time = time.time() - start_time
        
        print(f"   ⏱️  Respuesta recibida después de {elapsed_time:.2f} segundos")
        response.raise_for_status()
        
        # Obtener el contenido de la respuesta
        print(f"   📥 Status code: {response.status_code}")
        print(f"   📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   📥 Tamaño de respuesta: {len(response.content)} bytes")
        
        # Intentar parsear JSON
        try:
            jobs_data = response.json()
        except json.JSONDecodeError as e:
            print(f"   ❌ Error al parsear JSON: {e}")
            print(f"   📄 Primeros 500 caracteres de la respuesta:")
            print(f"   {response.text[:500]}")
            raise
        
        # Debug: mostrar estructura de la respuesta
        print(f"   📦 Tipo de respuesta: {type(jobs_data)}")
        
        if isinstance(jobs_data, dict):
            all_keys = list(jobs_data.keys())
            print(f"   📦 Keys en respuesta ({len(all_keys)}): {all_keys}")
            # Mostrar algunos valores para debugging
            for key in all_keys[:5]:
                value = jobs_data[key]
                if isinstance(value, (list, dict)):
                    print(f"      - {key}: {type(value).__name__} con {len(value) if hasattr(value, '__len__') else 'N/A'} elementos")
                else:
                    print(f"      - {key}: {str(value)[:100]}")
        
        # El API podría retornar directamente una lista o un objeto con una propiedad
        jobs = []
        
        if isinstance(jobs_data, list):
            jobs = jobs_data
            print(f"   ✅ Respuesta es una lista directa con {len(jobs)} elementos")
        elif isinstance(jobs_data, dict):
            # Intentar diferentes posibles estructuras comunes en APIs
            possible_keys = ["data", "jobOfferings", "results", "items", "jobs", "offers", "job_offerings", "content"]
            
            print(f"   🔍 Buscando empleos en las siguientes keys: {possible_keys}")
            for key in possible_keys:
                if key in jobs_data:
                    value = jobs_data[key]
                    print(f"      ✅ Encontrada key '{key}': tipo {type(value).__name__}")
                    if isinstance(value, list):
                        jobs = value
                        print(f"         → Lista con {len(jobs)} elementos")
                        break
                    elif isinstance(value, dict):
                        # Podría ser un objeto con más estructura
                        print(f"         → Es un dict, buscando dentro...")
                        # Intentar buscar dentro de este dict
                        for sub_key in possible_keys:
                            if sub_key in value and isinstance(value[sub_key], list):
                                jobs = value[sub_key]
                                print(f"            → Encontrada lista en '{key}.{sub_key}' con {len(jobs)} elementos")
                                break
                        if jobs:
                            break
            
            # Si aún no encontramos una lista, verificar si el dict completo es un empleo
            if not jobs:
                print(f"   🔍 No se encontró lista en keys conocidas, verificando si es un empleo único...")
                # Verificar si el dict tiene campos de empleo
                job_fields = ["identifier", "title", "name", "@type", "jobPosting"]
                found_fields = [field for field in job_fields if field in jobs_data]
                if found_fields:
                    print(f"      ✅ Encontrados campos de empleo: {found_fields}")
                    jobs = [jobs_data]
                    print(f"         → Tratando como un empleo único")
                else:
                    # Mostrar todas las keys para debugging
                    print(f"      ❌ No se encontraron campos de empleo conocidos")
                    print(f"      📋 Todas las keys disponibles: {list(jobs_data.keys())}")
                    # Intentar buscar recursivamente
                    print(f"      🔍 Buscando recursivamente en la estructura...")
                    def find_list_in_dict(d, path=""):
                        if isinstance(d, list) and len(d) > 0:
                            # Verificar si el primer elemento parece un empleo
                            if isinstance(d[0], dict) and any(field in d[0] for field in job_fields):
                                return d, path
                        elif isinstance(d, dict):
                            for k, v in d.items():
                                result = find_list_in_dict(v, f"{path}.{k}" if path else k)
                                if result:
                                    return result
                        return None
                    
                    result = find_list_in_dict(jobs_data)
                    if result:
                        jobs, found_path = result
                        print(f"      ✅ Encontrada lista en ruta: {found_path} ({len(jobs)} elementos)")
                    else:
                        print(f"      ❌ No se encontró ninguna lista de empleos en la estructura")
        
        if not jobs:
            print(f"   ⚠️  No se encontraron empleos en la respuesta")
            print(f"   📄 Mostrando estructura completa de la respuesta (primeros 1000 chars):")
            print(f"   {json.dumps(jobs_data, indent=2, ensure_ascii=False)[:1000]}")
        else:
            print(f"✅ Total de ofertas obtenidas: {len(jobs)}")
            if jobs and len(jobs) > 0:
                first_job = jobs[0]
                job_id = first_job.get('identifier') or first_job.get('id') or 'N/A'
                job_title = first_job.get('title') or first_job.get('name') or 'N/A'
                print(f"   - Primer empleo (sample):")
                print(f"      ID: {job_id}")
                print(f"      Título: {job_title[:80]}")
                if isinstance(first_job, dict):
                    print(f"      Keys del primer empleo: {list(first_job.keys())[:10]}")
        
        return jobs
        
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout al obtener ofertas de empleo después de {timeout} segundos")
        print(f"   ⚠️  La API puede tardar más de lo esperado. Intenta aumentar el timeout con --timeout o verifica la conexión.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener ofertas de empleo: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   - Status code: {e.response.status_code}")
            try:
                print(f"   - Response: {e.response.text[:500]}")
            except:
                print(f"   - Response: (no se pudo leer)")
        else:
            print(f"   ⚠️  No se recibió respuesta del servidor")
            print(f"   💡 Verifica tu conexión a internet y que el endpoint esté disponible")
        raise


def format_salary(base_salary):
    """
    Formatea el salario desde el objeto baseSalary del JSON.
    """
    if not base_salary:
        return None
    
    currency = base_salary.get("currency", "CLP")
    min_value = base_salary.get("minValue")
    max_value = base_salary.get("maxValue")
    
    # Convertir a int si son números
    try:
        if min_value is not None:
            min_value = int(min_value)
        if max_value is not None:
            max_value = int(max_value)
    except (ValueError, TypeError):
        pass
    
    # Formatear con separador de miles
    def format_number(num):
        if num is None:
            return None
        return f"{num:,}".replace(",", ".")
    
    if min_value and max_value:
        if min_value == max_value:
            return f"{format_number(min_value)} {currency}"
        return f"{format_number(min_value)} - {format_number(max_value)} {currency}"
    elif min_value:
        return f"Desde {format_number(min_value)} {currency}"
    elif max_value:
        return f"Hasta {format_number(max_value)} {currency}"
    else:
        return None


def parse_date(date_str):
    """
    Parsea una fecha desde el formato del API.
    """
    if not date_str:
        return None
    
    try:
        # El formato puede ser "2023-12-12T00:00:00-03:00" o "2023/12/18"
        if "T" in date_str:
            # Formato ISO con timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.date()
        elif "/" in date_str:
            # Formato "2023/12/18"
            dt = datetime.strptime(date_str, "%Y/%m/%d")
            return dt.date()
        else:
            # Intentar otros formatos comunes
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.date()
    except Exception as e:
        print(f"   ⚠️  Error al parsear fecha '{date_str}': {e}")
        return None


def analyze_area_subarea(title, description, occupational_category=None):
    """
    Analiza el título, descripción y categoría ocupacional para determinar área y subárea.
    """
    if not title and not description:
        return None, None
    
    # Combinar título, descripción y categoría para análisis
    text_to_analyze = f"{title or ''} {description or ''} {occupational_category or ''}".strip()
    
    if not text_to_analyze:
        return None, None
    
    print(f"   🔍 Analizando texto para área/subárea: '{text_to_analyze[:100]}...'")
    
    try:
        # Normalizar el texto para búsqueda
        text_lower = _norm(text_to_analyze).lower()
        
        # Mapeo de palabras clave a áreas (prioridad: más específicas primero)
        area_keywords = {
            "Gastronomía": [
                "cocina", "chef", "restaurante", "gastronomía", "gastronomia", 
                "alimentos", "comida", "manipulador", "manipuladora", "ayudante de cocina",
                "cocinero", "cocinera", "pastelero", "pastelera"
            ],
            "Salud": [
                "salud", "médico", "medico", "hospital", "clínica", "clinica", 
                "enfermería", "enfermeria", "enfermero", "enfermera", "paramédico", "paramedico"
            ],
            "Construcción": [
                "construcción", "construccion", "obra", "arquitectura", 
                "edificación", "edificacion", "maestro", "obrero", "albañil"
            ],
            "Transporte": [
                "transporte", "logística", "logistica", "conductor", "chofer",
                "transit", "vehículos", "vehiculos", "repartidor", "delivery"
            ],
            "Turismo": [
                "turismo", "hotel", "hotelería", "hoteleria", "recepción", 
                "recepcion", "viajes", "guía", "guia", "tour"
            ],
            "Finanzas": [
                "finanzas", "financiero", "contabilidad", "contador", 
                "auditoría", "auditoria", "banco", "bancario"
            ],
            "Recursos Humanos": [
                "recursos humanos", "rrhh", "hr", "reclutamiento", 
                "selección", "seleccion", "talento humano"
            ],
            "Tecnología": [
                "tecnología", "tecnologia", "tech", "informática", "informatica", 
                "software", "sistemas", "it", "programador", "desarrollador",
                "developer", "ingeniero de sistemas"
            ],
            "Educación": [
                "educación", "educacion", "docente", "profesor", "profesora",
                "maestro", "maestra", "enseñanza", "ensenanza", "pedagogía", "pedagogia"
            ],
            "Diseño": [
                "diseño", "diseno", "diseñador", "disenador", "ux", "ui", 
                "gráfico", "grafico", "diseñador gráfico", "designer"
            ],
            "Ventas": [
                "ventas", "vendedor", "vendedora", "comercial", "retail", 
                "tienda", "atención al cliente", "atencion al cliente"
            ],
            "Operario": [
                "operario", "operadora", "operador", "producción", "produccion", 
                "manufactura", "fábrica", "fabrica", "ensamblador"
            ],
            "Servicios Generales": [
                "servicios", "mantenimiento", "limpieza", "aseo", 
                "seguridad", "vigilante", "portero", "porteria"
            ],
        }
        
        # Buscar área por palabras clave (en orden de prioridad)
        area = None
        subarea = None
        
        # Primero intentar con parse_prompt para aprovechar la lógica existente
        try:
            include, exclude, salary_min, currency = parse_prompt(text_to_analyze)
            if include.get("area"):
                detected_area = include["area"][0] if isinstance(include["area"], list) else include["area"]
                area = detected_area
                print(f"   ✅ Área detectada por NLP: {area}")
        except Exception as e:
            print(f"   ⚠️  Error en parse_prompt: {e}")
        
        # Si no se encontró área con NLP, usar búsqueda por palabras clave
        if not area:
            # Buscar en orden de prioridad (áreas más específicas primero)
            for area_name, keywords in area_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    area = area_name
                    print(f"   ✅ Área detectada por palabras clave: {area}")
                    break
        
        # Determinar subárea basada en el área y palabras específicas
        if area and text_lower:
            # Subáreas específicas por área
            if area == "Gastronomía":
                if any(word in text_lower for word in ["chef", "cocinero", "cocinera"]):
                    subarea = "Cocina"
                elif any(word in text_lower for word in ["pastelero", "pastelera", "repostería", "reposteria"]):
                    subarea = "Repostería"
                elif any(word in text_lower for word in ["bar", "bartender", "mesero", "mesera"]):
                    subarea = "Servicio"
                else:
                    subarea = "Ayudante de Cocina"
            
            elif area == "Tecnología":
                if any(word in text_lower for word in ["desarrollador", "developer", "programador"]):
                    subarea = "Desarrollo"
                elif any(word in text_lower for word in ["sistemas", "infraestructura", "devops"]):
                    subarea = "Infraestructura"
                elif any(word in text_lower for word in ["diseño", "ux", "ui"]):
                    subarea = "Diseño"
                else:
                    subarea = "Sistemas"
            
            elif area == "Salud":
                if any(word in text_lower for word in ["enfermería", "enfermeria", "enfermero", "enfermera"]):
                    subarea = "Enfermería"
                elif any(word in text_lower for word in ["médico", "medico", "doctor"]):
                    subarea = "Medicina"
                else:
                    subarea = "Atención de Salud"
            
            elif area == "Operario":
                if any(word in text_lower for word in ["producción", "produccion"]):
                    subarea = "Producción"
                elif any(word in text_lower for word in ["ensamblaje", "ensamblador"]):
                    subarea = "Ensamblaje"
                else:
                    subarea = "Operaciones"
        
        if area:
            print(f"   📊 Resultado: Área={area}, Subárea={subarea or 'N/A'}")
        
        return area, subarea
        
    except Exception as e:
        print(f"   ⚠️  Error al analizar área/subárea: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def process_job_offering(job_data, source):
    """
    Procesa una oferta de empleo individual y la inserta en la base de datos.
    """
    print("\n" + "-" * 80)
    print(f"📋 Procesando oferta: {job_data.get('identifier', 'N/A')}")
    print("-" * 80)
    
    # Extraer datos básicos
    identifier = job_data.get("identifier")
    
    # Limpiar título: puede venir en "title" o "name", y puede tener el formato "[ID] Título"
    title = job_data.get("title") or job_data.get("name", "")
    if identifier and title.startswith(f"[{identifier}]"):
        title = title.replace(f"[{identifier}]", "").strip()
    # También limpiar si tiene el formato al inicio
    if title and title.startswith("["):
        # Eliminar cualquier patrón [XXX] al inicio
        title = re.sub(r'^\[\d+[-\w]*\]\s*', '', title).strip()
    
    description = job_data.get("description", "")
    url = job_data.get("url", "")
    
    print(f"   - ID: {identifier}")
    print(f"   - Título: {title}")
    print(f"   - URL: {url}")
    if description:
        print(f"   - Descripción (primeros 100 chars): {description[:100]}...")
    
    # Company
    hiring_org = job_data.get("hiringOrganization", {})
    company_name = hiring_org.get("name")
    if not company_name:
        # Intentar obtener de la descripción de la organización
        company_name = hiring_org.get("description", "Empresa no especificada")
    
    company, _ = get_or_create(Company, name=company_name)
    print(f"   - Empresa: {company_name}")
    
    # Location
    location = None
    job_location = job_data.get("jobLocation", {})
    location_address = job_location.get("address")
    
    if location_address:
        location, _ = get_or_create(Location, raw_text=location_address)
        print(f"   - Ubicación: {location_address}")
    else:
        # Intentar obtener de hiringOrganization
        org_address = hiring_org.get("address")
        if org_address:
            location, _ = get_or_create(Location, raw_text=org_address)
            print(f"   - Ubicación (desde org): {org_address}")
    
    # Fechas
    published_date = parse_date(job_data.get("datePosted"))
    if published_date:
        print(f"   - Fecha publicación: {published_date}")
    
    # Salario
    base_salary = job_data.get("baseSalary", {})
    salary_text = format_salary(base_salary)
    if salary_text:
        print(f"   - Salario: {salary_text}")
    
    # Jornada de trabajo
    workday = job_data.get("workHours")
    if workday:
        # Normalizar valores comunes
        workday_lower = workday.lower()
        if "completa" in workday_lower or "full" in workday_lower:
            workday = "Jornada Completa"
        elif "parcial" in workday_lower or "part" in workday_lower:
            workday = "Part-time"
        print(f"   - Jornada: {workday}")
    
    # Tipo de contrato
    contract_type = job_data.get("employmentType")
    if contract_type:
        print(f"   - Tipo contrato: {contract_type}")
    
    # Experiencia
    experience = job_data.get("experienceRequirements")
    if experience:
        print(f"   - Experiencia: {experience}")
    
    # Educación
    education = job_data.get("educationRequirements")
    if education:
        print(f"   - Educación: {education}")
    
    # Múltiples vacantes
    total_openings = job_data.get("totalJobOpenings", 1)
    multiple_vacancies = total_openings > 1
    if multiple_vacancies:
        print(f"   - Múltiples vacantes: {total_openings}")
    
    # Analizar área y subárea
    occupational_category = job_data.get("occupationalCategory", {})
    category_name = occupational_category.get("name") if isinstance(occupational_category, dict) else None
    area, subarea = analyze_area_subarea(title, description, category_name)
    
    # Accesibilidad y transporte (buscar en descripción)
    description_lower = (description or "").lower()
    accessibility_mentioned = any(keyword in description_lower for keyword in [
        "accesibilidad", "discapacidad", "silla de ruedas", "rampa", "ascensor",
        "incluyente", "inclusivo", "baño accesible"
    ])
    transport_mentioned = any(keyword in description_lower for keyword in [
        "transporte", "bus", "metro", "movi", "terminal", "transantiago"
    ])
    
    if accessibility_mentioned:
        print(f"   - ✅ Accesibilidad mencionada")
    if transport_mentioned:
        print(f"   - ✅ Transporte mencionado")
    
    # Crear o actualizar el JobPosting
    try:
        job, created = JobPosting.objects.get_or_create(
            url=url,
            defaults={
                "source": source,
                "source_job_id": identifier,
                "title": title,
                "company": company,
                "location": location,
                "published_date": published_date,
                "description": description,
                "workday": workday,
                "contract_type": contract_type,
                "salary_text": salary_text,
                "accessibility_mentioned": accessibility_mentioned,
                "transport_mentioned": transport_mentioned,
                "multiple_vacancies": multiple_vacancies,
                "area": area,
                "subarea": subarea,
                "min_experience": experience,
                "min_education": education,
            }
        )
        
        if created:
            print(f"   ✅ Empleo creado exitosamente (ID: {job.id})")
        else:
            print(f"   ℹ️  Empleo ya existe (ID: {job.id})")
            # Actualizar campos si es necesario
            job.title = title
            job.company = company
            job.location = location
            job.published_date = published_date
            job.description = description
            job.workday = workday
            job.contract_type = contract_type
            job.salary_text = salary_text
            job.accessibility_mentioned = accessibility_mentioned
            job.transport_mentioned = transport_mentioned
            job.multiple_vacancies = multiple_vacancies
            job.area = area
            job.subarea = subarea
            job.min_experience = experience
            job.min_education = education
            job.save()
            print(f"   ✅ Empleo actualizado")
        
        return job, created
        
    except Exception as e:
        print(f"   ❌ Error al crear/actualizar empleo: {e}")
        import traceback
        traceback.print_exc()
        return None, False


class Command(BaseCommand):
    help = "Importa empleos desde el API del Servicio Nacional de Empleo (BNE)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Número máximo de empleos a obtener por request (default: 100)"
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Offset para paginación (default: 0)"
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Timeout en segundos para las peticiones HTTP (default: 60). La API suele tardar 16-20 segundos."
        )

    def handle(self, *args, **options):
        limit = options.get("limit", 100)
        offset = options.get("offset", 0)
        timeout = options.get("timeout", 60)
        
        print("\n" + "=" * 80)
        print("🚀 INICIANDO IMPORTACIÓN DE EMPLEOS DESDE BNE")
        print("=" * 80)
        print(f"   - Límite: {limit}")
        print(f"   - Offset: {offset}")
        print(f"   - Timeout: {timeout} segundos")
        print("=" * 80 + "\n")
        
        try:
            # 1. Obtener token
            access_token = get_access_token(timeout=timeout)
            
            # 2. Obtener ofertas de empleo
            jobs = fetch_job_offerings(access_token, limit=limit, offset=offset, timeout=timeout)
            
            if not jobs:
                print("\n⚠️  No se obtuvieron ofertas de empleo")
                return
            
            # 3. Obtener o crear Source
            source, _ = get_or_create(Source, name=SOURCE_NAME)
            print(f"\n📦 Fuente: {source.name}")
            
            # 4. Procesar cada oferta
            print(f"\n🔄 Procesando {len(jobs)} ofertas de empleo...\n")
            
            created_count = 0
            updated_count = 0
            error_count = 0
            
            for i, job_data in enumerate(jobs, 1):
                print(f"\n[{i}/{len(jobs)}]")
                try:
                    job, created = process_job_offering(job_data, source)
                    if job:
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"   ❌ Error procesando oferta {i}: {e}")
                    error_count += 1
                    import traceback
                    traceback.print_exc()
            
            # 5. Resumen
            print("\n" + "=" * 80)
            print("✅ IMPORTACIÓN COMPLETADA")
            print("=" * 80)
            print(f"   - Total procesados: {len(jobs)}")
            print(f"   - Creados: {created_count}")
            print(f"   - Actualizados: {updated_count}")
            print(f"   - Errores: {error_count}")
            print("=" * 80 + "\n")
            
        except Exception as e:
            print(f"\n❌ Error fatal en la importación: {e}")
            import traceback
            traceback.print_exc()
            raise

