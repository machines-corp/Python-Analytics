from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .nlp import parse_prompt, parse_simple_response, parse_complex_intent, parse_job_selection, get_industries_from_db, get_modalities_from_db, get_areas_from_db, get_seniorities_from_db, get_locations_from_db, get_roles_from_db
from .engine import decide_jobs
from .models import JobPosting, Conversation
from django.db import ProgrammingError, OperationalError
from .serializers import ConversationSerializer
from .flow import next_missing_slot, question_for, get_encouraging_response


class JobSearchView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt", "")
        topn = int(request.data.get("topn", 3))

        # Extrae lista de roles actuales (para ayudar al parser)
        roles = list(Job.objects.values_list("role", flat=True).distinct())
        include, exclude, salary_min, currency = parse_prompt(prompt, roles)

        results, steps = decide_jobs(include, exclude, salary_min, currency, topn=topn)

        return Response({
            "prompt": prompt,
            "include": include,
            "exclude": exclude,
            "salary_min": salary_min,
            "currency": currency,
            "results": results,
            "trace": steps
        }, status=status.HTTP_200_OK)


def _roles():
    try:
        return list(JobPosting.objects.values_list("title", flat=True).distinct())
    except (ProgrammingError, OperationalError):
        return []

def _merge_state_with_prompt(state: dict, prompt: str):
    """Intenta parsear el texto y completar slots automáticamente."""
    # Primero verificar si es una selección de empleo
    job_selection = parse_job_selection(prompt)
    if job_selection.get("action") == "select_job":
        return {}, {}, None, job_selection  # Retornar información de selección
    
    # Luego intentar parsing de intenciones complejas
    complex_intent = parse_complex_intent(prompt)
    if complex_intent:
        encouraging_response = None
        for key, value in complex_intent.items():
            if key in ["industry", "area", "modality", "seniority"]:
                encouraging_response = get_encouraging_response(key, value)
                break
        
        state.update(complex_intent)
        return {}, {}, encouraging_response, None
    
    # Después intentar parsing contextual si sabemos qué slot estamos llenando
    next_slot = next_missing_slot(state)
    encouraging_response = None
    
    if next_slot:
        # Usar parsing contextual para el slot específico
        contextual_result = parse_simple_response(prompt, next_slot)
        if contextual_result:
            # Generar respuesta empática para la elección
            for key, value in contextual_result.items():
                if key in ["industry", "area", "modality", "seniority"]:
                    encouraging_response = get_encouraging_response(key, value)
                    break
            
            state.update(contextual_result)
            return {}, {}, encouraging_response, None  # Retornar también la respuesta empática
    
    # Si no hay contexto o el parsing contextual falló, usar parsing completo
    include, exclude, salary_min, currency = parse_prompt(prompt, _roles())
    
    # map a nuestro state
    if include.get("industry"): 
        state["industry"] = include["industry"][0]
        encouraging_response = get_encouraging_response("industry", include["industry"][0])
    if include.get("area"):     
        state["area"] = include["area"][0]
        if not encouraging_response:
            encouraging_response = get_encouraging_response("area", include["area"][0])
    if include.get("role"):     state["role"] = include["role"][0]
    if include.get("seniority"):
        state["seniority"] = include["seniority"][0]
        if not encouraging_response:
            encouraging_response = get_encouraging_response("seniority", include["seniority"][0])
    if include.get("modality"): 
        state["modality"] = include["modality"][0]
        if not encouraging_response:
            encouraging_response = get_encouraging_response("modality", include["modality"][0])
    if include.get("location"): state["location"] = include["location"][0]

    if "exclude" not in state: state["exclude"] = []
    # exclude puede venir mapeado en varias keys; compactamos a lista de palabras prohibidas
    ex_values = []
    for k in ("role","area","modality","seniority","industry"):
        for v in (exclude.get(k) or []):
            ex_values.append(v)
    state["exclude"] = list(dict.fromkeys((state.get("exclude") or []) + ex_values))

    if salary_min:
        state["salary"] = {"min": salary_min, "currency": currency}
    return include, exclude, encouraging_response, None

def _serialize_job_results(results):
    """Convierte los resultados de empleos a diccionarios serializables para JSON."""
    serializable_results = []
    for job in results:
        serializable_job = {}
        for key, value in job.items():
            if hasattr(value, 'isoformat'):  # Para objetos date/datetime
                serializable_job[key] = value.isoformat()
            elif hasattr(value, '__dict__'):  # Para objetos complejos
                serializable_job[key] = str(value)
            else:
                serializable_job[key] = value
        serializable_results.append(serializable_job)
    return serializable_results

def _build_filters_from_state(state: dict):
    include = {}
    exclude = {}
    sal_min = None
    currency = None

    if v := state.get("industry"): include["industry"] = [v]
    if v := state.get("area"):     include["area"] = [v]
    if v := state.get("role"):     include["role"] = [v]
    if v := state.get("seniority"):include["seniority"] = [v]
    if v := state.get("modality"): include["modality"] = [v]
    if v := state.get("location"): include["location"] = [v]

    if ex := state.get("exclude"):
        # si el usuario guardó exclusiones como texto libre, las tratamos como exclusión de role/area
        # (puedes sofisticar esto con un parser igual al de parse_prompt)
        exclude["role"] = ex

    salary = state.get("salary")
    if isinstance(salary, dict) and salary.get("min"):
        sal_min = int(salary["min"])
        currency = salary.get("currency") or "USD"

    return include, exclude, sal_min, currency

class ChatStart(APIView):
    """Crea una nueva conversación y devuelve la primera pregunta."""
    def post(self, request):
        conv = Conversation.objects.create(state={}, history=[])
        first_slot = next_missing_slot(conv.state)
        q = question_for(first_slot)
        
        # Mensaje de bienvenida más conversacional
        welcome_message = f"¡Hola! 👋 Soy tu asistente de empleos y estoy aquí para ayudarte a encontrar el trabajo perfecto. Te haré algunas preguntas rápidas para entender mejor lo que buscas.\n\n{q}"
        
        conv.history.append({"role":"system","text": welcome_message})
        conv.save()
        return Response({"conversation_id": conv.id, "message": welcome_message}, status=201)

class ChatMessage(APIView):
    """
    Recibe una respuesta del usuario y devuelve:
    - la siguiente pregunta (si faltan slots), o
    - una recomendación (top 3) si ya hay suficiente info o si el usuario pide 'recomienda'/'listo'.
    """
    def post(self, request, conversation_id:int):
        text = (request.data.get("message") or "").strip()
        if not text:
            return Response({"error":"message vacío"}, status=400)

        try:
            conv = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({"error":"Conversación no encontrada"}, status=404)

        # Guarda mensaje
        conv.history.append({"role":"user","text": text})

        # Intenta mapear automáticamente lo que escribió al estado
        include, exclude, encouraging_response, job_selection = _merge_state_with_prompt(conv.state, text)

        # Si el usuario está seleccionando un empleo específico
        if job_selection and job_selection.get("action") == "select_job":
            # Buscar el empleo en los resultados anteriores
            selected_index = job_selection.get("selected_job_index", 0)
            
            # Obtener los últimos resultados de la conversación
            last_results = conv.state.get("last_results", [])
            if last_results and 0 <= selected_index < len(last_results):
                selected_job = last_results[selected_index]
                job_id = selected_job.get("id")
                
                if job_id:
                    # Construir respuesta con detalles del empleo
                    job_details_response = f"¡Excelente elección! 🎯 Te muestro todos los detalles del empleo que seleccionaste:\n\n"
                    job_details_response += f"📋 **{selected_job.get('title', 'Sin título')}**\n"
                    job_details_response += f"🏢 **Empresa:** {selected_job.get('company', {}).get('name', 'No especificada')}\n"
                    job_details_response += f"📍 **Ubicación:** {selected_job.get('location', {}).get('raw_text', 'No especificada')}\n"
                    job_details_response += f"💼 **Área:** {selected_job.get('area', 'No especificada')}\n"
                    job_details_response += f"🏠 **Modalidad:** {selected_job.get('work_modality', 'No especificada')}\n"
                    job_details_response += f"💰 **Salario:** {selected_job.get('salary_text', 'No especificado')}\n"
                    job_details_response += f"🔗 **Ver empleo completo:** {selected_job.get('url', '#')}\n\n"
                    job_details_response += f"💡 ¿Te interesa este empleo? ¿Quieres que te ayude con algo más?"
                    
                    conv.history.append({"role":"system","text": job_details_response})
                    conv.save()
                    return Response({
                        "type": "job_details", 
                        "message": job_details_response,
                        "job_id": job_id,
                        "job_data": selected_job
                    })
                else:
                    conv.history.append({"role":"system","text": "Lo siento, no pude encontrar los detalles completos de ese empleo. ¿Podrías intentar seleccionar otro?"})
                    conv.save()
                    return Response({"type": "error", "message": "No se pudieron obtener los detalles del empleo"})
            else:
                conv.history.append({"role":"system","text": "No tengo empleos disponibles para seleccionar. Primero necesito mostrarte algunas opciones. ¿Quieres que busque empleos para ti?"})
                conv.save()
                return Response({"type": "error", "message": "No hay empleos disponibles para seleccionar"})

        # Si el usuario pide recomendar ya:
        if any(w in text.lower() for w in ["listo","recomienda","muestrame","sugerencias","ofrecer","buscar","empleos","trabajos"]):
            include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
            results, steps = decide_jobs(include, exclude, sal_min, currency, topn=3)
            
            # Guardar resultados en el estado para selección posterior
            conv.state["last_results"] = _serialize_job_results(results)
            conv.save()
            
            reply = {"type": "results", "results": results, "trace": steps}
            conv.history.append({"role":"system","text":"¡Perfecto! Te dejo mis mejores sugerencias basadas en tus preferencias. 🎯"})
            conv.save()
            return Response(reply)

        # Si faltan slots, pregunta el siguiente
        nxt = next_missing_slot(conv.state)
        if nxt:
            # Si ya tenemos información suficiente (al menos 2 campos), ofrecer mostrar empleos
            filled_slots = sum(1 for k, v in conv.state.items() if v and v not in (None, "", []))
            if filled_slots >= 2:
                q = question_for(nxt)
                
                # Construir mensaje con respuesta empática y opción de mostrar empleos
                message = q
                if encouraging_response:
                    message = f"{encouraging_response}\n\n{q}"
                
                message += "\n\n💡 ¿O prefieres que te muestre empleos con la información que ya tengo? Solo escribe 'mostrar empleos' o 'buscar'."
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({"type":"question", "message": message, "filled": conv.state})
            else:
                q = question_for(nxt)
                
                # Construir mensaje con respuesta empática si la hay
                message = q
                if encouraging_response:
                    message = f"{encouraging_response}\n\n{q}"
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({"type":"question", "message": message, "filled": conv.state})

        # Si no faltan slots, devuelve recomendaciones
        include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
        results, steps = decide_jobs(include, exclude, sal_min, currency, topn=3)
        
        # Guardar resultados en el estado para selección posterior
        conv.state["last_results"] = _serialize_job_results(results)
        conv.save()
        
        # Mensaje final empático
        final_message = "¡Excelente! Ya tengo toda la información que necesito. Te dejo mis mejores sugerencias:"
        if encouraging_response:
            final_message = f"{encouraging_response}\n\n{final_message}"
        
        conv.history.append({"role":"system","text": final_message})
        conv.save()
        return Response({"type":"results", "results": results, "trace": steps, "filled": conv.state})


class TaxonomyView(APIView):
    """
    Endpoint para obtener la taxonomía disponible en la base de datos
    """
    def get(self, request):
        try:
            taxonomy = {
                "industries": get_industries_from_db(),
                "modalities": get_modalities_from_db(),
                "areas": get_areas_from_db(),
                "seniorities": get_seniorities_from_db(),
                "locations": get_locations_from_db(),
                "roles": get_roles_from_db()[:50],  # Limitar a 50 roles para no sobrecargar
                "total_jobs": JobPosting.objects.count(),
                "companies": list(JobPosting.objects.values_list('company__name', flat=True).distinct()[:20])  # Top 20 empresas
            }
            return Response(taxonomy, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobDetailsView(APIView):
    """
    Endpoint para obtener detalles completos de un empleo específico
    """
    def get(self, request, job_id):
        try:
            job = JobPosting.objects.select_related('company', 'location', 'source').get(id=job_id)
            
            # Obtener información completa del empleo
            job_details = {
                "id": job.id,
                "title": job.title,
                "company": {
                    "name": job.company.name,
                    "verified": job.company.verified,
                    "rating": job.company.rating
                },
                "location": {
                    "raw_text": job.location.raw_text if job.location else None
                },
                "source": {
                    "name": job.source.name,
                    "url": job.url
                },
                "description": job.description,
                "work_modality": job.work_modality,
                "contract_type": job.contract_type,
                "workday": job.workday,
                "salary_text": job.salary_text,
                "area": job.area,
                "subarea": job.subarea,
                "min_experience": job.min_experience,
                "min_education": job.min_education,
                "published_date": job.published_date,
                "accessibility_mentioned": job.accessibility_mentioned,
                "transport_mentioned": job.transport_mentioned,
                "disability_friendly": job.disability_friendly,
                "multiple_vacancies": job.multiple_vacancies,
                "created_at": job.created_at,
                "updated_at": job.updated_at
            }
            
            return Response(job_details, status=status.HTTP_200_OK)
        except JobPosting.DoesNotExist:
            return Response({"error": "Empleo no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)