from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .nlp import parse_prompt, parse_simple_response, parse_complex_intent, parse_job_selection, parse_more_jobs_intent, parse_change_slot_intent, parse_show_jobs_intent, get_industries_from_db, get_modalities_from_db, get_areas_from_db, get_seniorities_from_db, get_locations_from_db, get_roles_from_db
from .engine import decide_jobs, get_job_pagination_info
from .models import JobPosting, Conversation
from django.db import ProgrammingError, OperationalError
from .serializers import ConversationSerializer
from .flow import next_missing_slot, question_for, get_encouraging_response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import transaction
from .models import JobPosting, Source, Company, Location, Benefit

class JobSearchView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt", "")
        topn = int(request.data.get("topn", 3))

        # Extrae lista de roles actuales (para ayudar al parser)
        roles = list(Job.objects.values_list("role", flat=True).distinct())
        include, exclude, salary_min, currency = parse_prompt(prompt, roles)

        results, steps, metadata = decide_jobs(include, exclude, salary_min, currency, topn=topn)

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
    print("\n" + "="*80)
    print("💬 _MERGE_STATE_WITH_PROMPT - Procesando mensaje del usuario")
    print("="*80)
    print(f"📥 Prompt: '{prompt}'")
    print(f"📋 Estado actual: {state}")
    
    # Primero verificar si es una selección de empleo
    job_selection = parse_job_selection(prompt)
    if job_selection.get("action") == "select_job":
        print(f"✅ Detectado: Selección de empleo - {job_selection}")
        print("="*80)
        return {}, {}, None, job_selection  # Retornar información de selección
    
    # Verificar si quiere cambiar un slot específico
    change_slot_intent = parse_change_slot_intent(prompt)
    if change_slot_intent.get("action") == "change_slot":
        slot_to_change = change_slot_intent.get("slot")
        new_value = change_slot_intent.get("new_value")
        print(f"✅ Detectado: Cambio de slot '{slot_to_change}'")
        if new_value:
            print(f"   - Nuevo valor detectado: {new_value}")
        else:
            print(f"   - Esperando nuevo valor en siguiente mensaje")
        print("="*80)
        return {}, {}, None, change_slot_intent  # Retornar información de cambio de slot
    
    # Verificar si pide más empleos o diferentes empleos
    more_jobs_intent = parse_more_jobs_intent(prompt)
    if more_jobs_intent.get("action") == "more_jobs":
        print(f"✅ Detectado: Solicitud de más empleos - {more_jobs_intent}")
        print("="*80)
        # NO modificar el estado cuando se piden más empleos
        return {}, {}, None, more_jobs_intent  # Retornar información de solicitud de más empleos
    
    # Verificar si quiere ver empleos ahora
    show_jobs_intent = parse_show_jobs_intent(prompt)
    if show_jobs_intent.get("action") == "show_jobs":
        print(f"✅ Detectado: Solicitud de mostrar empleos - {show_jobs_intent}")
        print("="*80)
        return {}, {}, None, show_jobs_intent  # Retornar información de solicitud de mostrar empleos
    
    # Luego intentar parsing de intenciones complejas
    complex_intent = parse_complex_intent(prompt)
    if complex_intent:
        print(f"✅ Detectado: Intención compleja - {complex_intent}")
        encouraging_response = None
        for key, value in complex_intent.items():
            # Solo actualizar slots que tienen valores válidos Y que no estén ya definidos
            if key in ["industry", "area", "modality", "seniority", "location", "accessibility", "transport"]:
                if value and value not in (None, "", []):
                    # NO sobrescribir si ya existe un valor en el estado
                    if key not in state or not state[key] or state[key] in (None, "", []):
                        state[key] = value
                        if not encouraging_response:
                            encouraging_response = get_encouraging_response(key, value)
                        print(f"   ✅ Slot '{key}' actualizado a: {value}")
                    else:
                        print(f"   ⚠️  Slot '{key}' ya tiene valor: {state[key]}, ignorando: {value}")
        
        print(f"📋 Estado actualizado: {state}")
        print("="*80)
        return {}, {}, encouraging_response, None
    
    # Después intentar parsing contextual si sabemos qué slot estamos llenando
    # O si estamos cambiando un slot específico
    changing_slot = state.get("changing_slot")
    next_slot = changing_slot if changing_slot else next_missing_slot(state)
    encouraging_response = None
    action_intent = None  # Inicializar action_intent
    print(f"🔍 Slot siguiente: {next_slot} {'(cambiando)' if changing_slot else '(normal)'}")
    
    # Si estamos cambiando un slot, intentar parsear el nuevo valor directamente
    if changing_slot:
        parsed_changing = parse_simple_response(prompt, changing_slot)
        if parsed_changing and changing_slot in parsed_changing:
            state[changing_slot] = parsed_changing[changing_slot]
            state.pop("changing_slot", None)
            encouraging_response = get_encouraging_response(changing_slot, parsed_changing[changing_slot])
            print(f"   ✅ Slot '{changing_slot}' actualizado durante cambio a: {parsed_changing[changing_slot]}")
            print(f"📋 Estado actualizado: {state}")
            print("="*80)
            return {}, {}, encouraging_response, {"action": "slot_change_complete", "slot": changing_slot, "value": parsed_changing[changing_slot]}
    
    # Si el usuario dice directamente un valor cuando ya tiene un slot lleno del mismo tipo,
    # interpretarlo como cambio (ej: dice "tecnología" cuando ya tiene industria "finanzas")
    if not changing_slot and not action_intent:
        # Verificar si el prompt parece ser un valor nuevo para un slot existente
        from empleos.nlp import get_current_industries, get_current_areas, get_current_modalities
        
        available_industries = get_current_industries()
        available_areas = get_current_areas()
        available_modalities = get_current_modalities()
        
        prompt_lower = prompt.lower()
        
        # Si el usuario dice directamente una industria cuando ya tiene industria
        if "industry" in state and state.get("industry"):
            for ind in available_industries:
                if ind.lower() in prompt_lower and state["industry"].lower() != ind.lower():
                    # Intentar parsear como industria
                    parsed_industry = parse_simple_response(prompt, "industry")
                    if parsed_industry.get("industry"):
                        state["industry"] = parsed_industry["industry"]
                        encouraging_response = get_encouraging_response("industry", parsed_industry["industry"])
                        print(f"   ✅ Detectado cambio implícito de industria: '{state.get('industry')}' → '{parsed_industry['industry']}'")
                        print(f"📋 Estado actualizado: {state}")
                        print("="*80)
                        return {}, {}, encouraging_response, {"action": "slot_change_complete", "slot": "industry", "value": parsed_industry["industry"]}
        
        # Si el usuario dice directamente un área funcional cuando ya tiene área
        if "area" in state and state.get("area"):
            for area in available_areas:
                if area.lower() in prompt_lower and state["area"].lower() != area.lower():
                    # Intentar parsear como área
                    parsed_area = parse_simple_response(prompt, "area")
                    if parsed_area.get("area"):
                        state["area"] = parsed_area["area"]
                        encouraging_response = get_encouraging_response("area", parsed_area["area"])
                        print(f"   ✅ Detectado cambio implícito de área: '{state.get('area')}' → '{parsed_area['area']}'")
                        print(f"📋 Estado actualizado: {state}")
                        print("="*80)
                        return {}, {}, encouraging_response, {"action": "slot_change_complete", "slot": "area", "value": parsed_area["area"]}
        
        # Si el usuario dice directamente una modalidad cuando ya tiene modalidad
        if "modality" in state and state.get("modality"):
            for mod in available_modalities:
                if mod.lower() in prompt_lower and state["modality"].lower() != mod.lower():
                    # Intentar parsear como modalidad
                    parsed_modality = parse_simple_response(prompt, "modality")
                    if parsed_modality.get("modality"):
                        state["modality"] = parsed_modality["modality"]
                        encouraging_response = get_encouraging_response("modality", parsed_modality["modality"])
                        print(f"   ✅ Detectado cambio implícito de modalidad: '{state.get('modality')}' → '{parsed_modality['modality']}'")
                        print(f"📋 Estado actualizado: {state}")
                        print("="*80)
                        return {}, {}, encouraging_response, {"action": "slot_change_complete", "slot": "modality", "value": parsed_modality["modality"]}
    
    if next_slot:
        # Usar parsing contextual para el slot específico
        contextual_result = parse_simple_response(prompt, next_slot)
        if contextual_result:
            print(f"✅ Parsing contextual exitoso: {contextual_result}")
            # Si estamos cambiando un slot, permitir sobrescribir
            for key, value in contextual_result.items():
                if value and value not in (None, "", []):
                    # Si estamos cambiando este slot específico, permitir sobrescribir
                    if changing_slot == key:
                        state[key] = value
                        state.pop("changing_slot", None)  # Limpiar flag de cambio
                        if not encouraging_response:
                            encouraging_response = get_encouraging_response(key, value)
                        print(f"   ✅ Slot '{key}' actualizado a: {value} (cambio permitido)")
                    # NO sobrescribir si ya existe un valor en el estado (solo si no estamos cambiando)
                    elif key not in state or not state[key] or state[key] in (None, "", []):
                        state[key] = value
                        if not encouraging_response:
                            encouraging_response = get_encouraging_response(key, value)
                        print(f"   ✅ Slot '{key}' actualizado a: {value}")
                    else:
                        print(f"   ⚠️  Slot '{key}' ya tiene valor: {state[key]}, ignorando: {value}")
            
            print(f"📋 Estado actualizado: {state}")
            print("="*80)
            return {}, {}, encouraging_response, None  # Retornar también la respuesta empática
        else:
            print(f"⚠️  Parsing contextual falló para '{next_slot}'")
    
    # Si no hay contexto o el parsing contextual falló, usar parsing completo
    print(f"🔄 Intentando parsing completo del prompt...")
    include, exclude, salary_min, currency = parse_prompt(prompt, _roles())
    print(f"📊 Resultado parsing:")
    print(f"   - include: {include}")
    print(f"   - exclude: {exclude}")
    print(f"   - salary_min: {salary_min}, currency: {currency}")
    
    # map a nuestro state - SOLO actualizar si hay valor en el parsing Y no existe ya
    if include.get("industry") and include["industry"]: 
        if "industry" not in state or not state["industry"]:
            state["industry"] = include["industry"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("industry", include["industry"][0])
            print(f"   ✅ Slot 'industry' actualizado a: {include['industry'][0]}")
        else:
            print(f"   ⚠️  Slot 'industry' ya tiene valor: {state['industry']}, ignorando: {include['industry'][0]}")
    if include.get("area") and include["area"]:     
        if "area" not in state or not state["area"]:
            state["area"] = include["area"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("area", include["area"][0])
            print(f"   ✅ Slot 'area' actualizado a: {include['area'][0]}")
        else:
            print(f"   ⚠️  Slot 'area' ya tiene valor: {state['area']}, ignorando: {include['area'][0]}")
    if include.get("role") and include["role"]:     
        if "role" not in state or not state["role"]:
            state["role"] = include["role"][0]
    if include.get("seniority") and include["seniority"]:
        if "seniority" not in state or not state["seniority"]:
            state["seniority"] = include["seniority"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("seniority", include["seniority"][0])
            print(f"   ✅ Slot 'seniority' actualizado a: {include['seniority'][0]}")
        else:
            print(f"   ⚠️  Slot 'seniority' ya tiene valor: {state['seniority']}, ignorando: {include['seniority'][0]}")
    if include.get("modality") and include["modality"]: 
        if "modality" not in state or not state["modality"]:
            state["modality"] = include["modality"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("modality", include["modality"][0])
            print(f"   ✅ Slot 'modality' actualizado a: {include['modality'][0]}")
        else:
            print(f"   ⚠️  Slot 'modality' ya tiene valor: {state['modality']}, ignorando: {include['modality'][0]}")
    if include.get("location") and include["location"]: 
        if "location" not in state or not state["location"]:
            state["location"] = include["location"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("location", include["location"][0])
            print(f"   ✅ Slot 'location' actualizado a: {include['location'][0]}")
        else:
            print(f"   ⚠️  Slot 'location' ya tiene valor: {state['location']}, ignorando: {include['location'][0]}")
    if include.get("accessibility") and include["accessibility"]:
        if "accessibility" not in state or not state["accessibility"]:
            state["accessibility"] = include["accessibility"][0]
            if not encouraging_response:
                encouraging_response = get_encouraging_response("accessibility", "sí")
            print(f"   ✅ Slot 'accessibility' actualizado")
        else:
            print(f"   ⚠️  Slot 'accessibility' ya tiene valor, ignorando nuevo valor")
    if include.get("transport") and include["transport"]:
        if "transport" not in state or not state["transport"]:
            state["transport"] = include["transport"][0]
            print(f"   ✅ Slot 'transport' actualizado")
        else:
            print(f"   ⚠️  Slot 'transport' ya tiene valor, ignorando nuevo valor")

    if "exclude" not in state: state["exclude"] = []
    # exclude puede venir mapeado en varias keys; compactamos a lista de palabras prohibidas
    ex_values = []
    for k in ("role","area","modality","seniority","industry"):
        for v in (exclude.get(k) or []):
            ex_values.append(v)
    state["exclude"] = list(dict.fromkeys((state.get("exclude") or []) + ex_values))

    if salary_min:
        state["salary"] = {"min": salary_min, "currency": currency}
        if not encouraging_response:
            encouraging_response = get_encouraging_response("salary", f"{salary_min} {currency}")
    
    print(f"📋 Estado final: {state}")
    print("="*80)
    return include, exclude, encouraging_response, None

def _serialize_job_results(results):
    """Convierte los resultados de empleos a diccionarios serializables para JSON."""
    # Los resultados ahora vienen como diccionarios desde engine._get_varied_results
    # ya con rating convertido a float, así que solo necesitamos serializar fechas
    serializable_results = []
    for job in results:
        serializable_job = job.copy()
        
        # Asegurar que las fechas sean serializables
        if 'published_date' in serializable_job and hasattr(serializable_job['published_date'], 'isoformat'):
            serializable_job['published_date'] = serializable_job['published_date'].isoformat()
        
        serializable_results.append(serializable_job)
    return serializable_results

def _get_filtered_state_for_frontend(state: dict):
    """
    Filtra el estado de la conversación para enviar solo los slots principales al frontend.
    Esto evita enviar información interna como 'last_results', 'current_offset', etc.
    """
    main_slots = ["industry", "area", "modality", "seniority", "location"]
    return {k: v for k, v in state.items() if k in main_slots}

def _build_filters_from_state(state: dict):
    print("\n" + "="*80)
    print("🔧 _BUILD_FILTERS_FROM_STATE - Construyendo filtros")
    print("="*80)
    print(f"📥 Estado recibido: {state}")
    
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
    if v := state.get("accessibility"): include["accessibility"] = [v]
    if v := state.get("transport"): include["transport"] = [v]

    if ex := state.get("exclude"):
        # si el usuario guardó exclusiones como texto libre, las tratamos como exclusión de role/area
        # (puedes sofisticar esto con un parser igual al de parse_prompt)
        exclude["role"] = ex

    salary = state.get("salary")
    if isinstance(salary, dict) and salary.get("min"):
        sal_min = int(salary["min"])
        currency = salary.get("currency") or "USD"

    print(f"📊 Filtros construidos:")
    print(f"   - include: {include}")
    print(f"   - exclude: {exclude}")
    print(f"   - sal_min: {sal_min}, currency: {currency}")
    print("="*80)
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

class ChatState(APIView):
    """
    Endpoint GET para obtener el estado actual de una conversación (slots).
    Útil para sincronizar el frontend con el estado real del backend.
    """
    def get(self, request, conversation_id: int):
        try:
            conv = Conversation.objects.get(id=conversation_id)
            print(f"\n📊 CHAT_STATE - Consultando estado de conversación {conversation_id}")
            print(f"📋 Estado completo en BD: {conv.state}")
            
            # Filtrar solo los slots principales para el frontend
            filtered_state = _get_filtered_state_for_frontend(conv.state)
            print(f"📤 Estado filtrado para frontend: {filtered_state}")
            
            # Contar slots completados
            main_slots = ["industry", "area", "modality", "seniority", "location"]
            filled_count = sum(1 for k in main_slots if conv.state.get(k) and conv.state.get(k) not in (None, "", []))
            
            response_data = {
                "conversation_id": conv.id,
                "state": filtered_state,
                "filled_count": filled_count,
                "total_slots": len(main_slots),
                "progress_percentage": round((filled_count / len(main_slots)) * 100),
            }
            
            print(f"✅ Respuesta enviada: {response_data}")
            return Response(response_data, status=200)
        except Conversation.DoesNotExist:
            print(f"❌ Conversación {conversation_id} no encontrada")
            return Response({"error": "Conversación no encontrada"}, status=404)
        except Exception as e:
            print(f"❌ Error al obtener estado: {e}")
            return Response({"error": str(e)}, status=500)

class ChatMessage(APIView):
    """
    Recibe una respuesta del usuario y devuelve:
    - la siguiente pregunta (si faltan slots), o
    - una recomendación (top 3) si ya hay suficiente info o si el usuario pide 'recomienda'/'listo'.
    """
    def post(self, request, conversation_id:int):
        print("\n" + "="*80)
        print("🚀 CHAT_MESSAGE - Nueva solicitud recibida")
        print("="*80)
        print(f"💬 Conversation ID: {conversation_id}")
        
        text = (request.data.get("message") or "").strip()
        print(f"📥 Mensaje: '{text}'")
        
        if not text:
            print("❌ Mensaje vacío")
            return Response({"error":"message vacío"}, status=400)

        try:
            conv = Conversation.objects.get(id=conversation_id)
            print(f"✅ Conversación encontrada: {conv.id}")
        except Conversation.DoesNotExist:
            print(f"❌ Conversación {conversation_id} no encontrada")
            return Response({"error":"Conversación no encontrada"}, status=404)

        # Guarda mensaje
        conv.history.append({"role":"user","text": text})

        # Intenta mapear automáticamente lo que escribió al estado
        include, exclude, encouraging_response, action_intent = _merge_state_with_prompt(conv.state, text)
        print(f"🔄 Después de merge_state:")
        print(f"   - include: {include}")
        print(f"   - exclude: {exclude}")
        print(f"   - action_intent: {action_intent}")

        # Si NO se detectó NADA (ninguna intención, ningún valor)
        # y estamos esperando una respuesta específica, significa que no se entendió
        if not action_intent and not include and not encouraging_response:
            print("⚠️ No se detectó ninguna intención ni valor - el usuario escribió algo no reconocible")
            nxt = next_missing_slot(conv.state)
            if nxt:
                q = question_for(nxt)
                # Mensaje empático indicando que no se entendió
                slot_labels = {
                    "industry": "industria",
                    "area": "área funcional",
                    "modality": "modalidad de trabajo",
                    "seniority": "nivel de experiencia",
                    "location": "ubicación"
                }
                slot_label = slot_labels.get(nxt, nxt)
                message = f"😕 Lo siento, no pude entender tu respuesta sobre {slot_label}. \n\n"
                
                # Dar opciones según el slot
                if nxt == "industry":
                    message += "Por favor, dime una **industria** como: Tecnología, Educación, Salud, Finanzas, Retail, etc."
                elif nxt == "area":
                    message += "Por favor, dime un **área funcional** como: Diseño, Desarrollo, Datos, Gastronomía, Cultura, Salud, etc."
                elif nxt == "modality":
                    message += "Por favor, dime una **modalidad** como: Remoto, Híbrido o Presencial."
                elif nxt == "seniority":
                    message += "Por favor, dime tu **nivel de experiencia**: Junior, Semi o Senior."
                elif nxt == "location":
                    message += "Por favor, dime una **ubicación** como: Santiago, Valparaíso, Región Metropolitana, etc."
                else:
                    message += q
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (unclear): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type":"unclear", 
                    "message": message, 
                    "filled": filtered_state
                })
        
        # Si se completó un cambio de slot (cuando el usuario da el nuevo valor directamente)
        if action_intent and action_intent.get("action") == "slot_change_complete":
            slot_changed = action_intent.get("slot")
            new_value = action_intent.get("value")
            
            slot_labels = {
                "industry": "industria",
                "area": "área funcional",
                "modality": "modalidad",
                "seniority": "nivel de experiencia",
                "location": "ubicación"
            }
            slot_label = slot_labels.get(slot_changed, slot_changed)
            
            message = f"✅ Perfecto, he actualizado la {slot_label} a '{new_value}'. "
            if encouraging_response:
                message = f"{encouraging_response}\n\n{message}"
            
            # Preguntar si quiere buscar empleos o agregar más información
            nxt = next_missing_slot(conv.state)
            if nxt:
                slot_labels_next = {
                    "industry": "industria",
                    "area": "área funcional",
                    "modality": "modalidad",
                    "seniority": "nivel de experiencia",
                    "location": "ubicación"
                }
                slot_label_next = slot_labels_next.get(nxt, nxt)
                message += f"¿Quieres agregar más información sobre la {slot_label_next} o buscar empleos ahora?"
            else:
                message += "¿Quieres buscar empleos ahora o agregar más criterios?"
            
            # Filtrar solo los slots principales para el frontend
            filtered_state = _get_filtered_state_for_frontend(conv.state)
            print(f"📤 Enviando estado actualizado (slot_change_complete): {filtered_state}")
            
            conv.history.append({"role":"system","text": message})
            conv.save()
            return Response({
                "type": "slot_change_complete", 
                "message": message, 
                "slot": slot_changed,
                "value": new_value,
                "filled": filtered_state
            })
        
        # Si el usuario quiere cambiar un slot específico
        if action_intent and action_intent.get("action") == "change_slot":
            slot_to_change = action_intent.get("slot")
            new_value = action_intent.get("new_value")
            
            # Si hay un nuevo valor en el mismo mensaje, actualizarlo
            if new_value:
                # Intentar parsear el nuevo valor
                parsed_new = parse_simple_response(new_value, slot_to_change)
                if parsed_new and slot_to_change in parsed_new:
                    conv.state[slot_to_change] = parsed_new[slot_to_change]
                    conv.state.pop("changing_slot", None)  # Limpiar flag de cambio
                    conv.save()
                    
                    slot_labels = {
                        "industry": "industria",
                        "area": "área funcional",
                        "modality": "modalidad",
                        "seniority": "nivel de experiencia",
                        "location": "ubicación"
                    }
                    slot_label = slot_labels.get(slot_to_change, slot_to_change)
                    message = f"✅ Perfecto, he actualizado la {slot_label} a '{parsed_new[slot_to_change]}'. "
                    
                    # Preguntar si quiere buscar empleos o agregar más información
                    nxt = next_missing_slot(conv.state)
                    if nxt:
                        slot_labels_next = {
                            "industry": "industria",
                            "area": "área funcional",
                            "modality": "modalidad",
                            "seniority": "nivel de experiencia",
                            "location": "ubicación"
                        }
                        slot_label_next = slot_labels_next.get(nxt, nxt)
                        message += f"¿Quieres agregar más información sobre la {slot_label_next} o buscar empleos ahora?"
                    else:
                        message += "¿Quieres buscar empleos ahora o agregar más criterios?"
                else:
                    # Si no se puede parsear, usar el valor directo
                    conv.state[slot_to_change] = new_value
                    conv.state.pop("changing_slot", None)  # Limpiar flag de cambio
                    conv.save()
                    
                    slot_labels = {
                        "industry": "industria",
                        "area": "área funcional",
                        "modality": "modalidad",
                        "seniority": "nivel de experiencia",
                        "location": "ubicación"
                    }
                    slot_label = slot_labels.get(slot_to_change, slot_to_change)
                    message = f"✅ Perfecto, he actualizado la {slot_label} a '{new_value}'. "
                    
                    # Preguntar si quiere buscar empleos o agregar más información
                    nxt = next_missing_slot(conv.state)
                    if nxt:
                        slot_labels_next = {
                            "industry": "industria",
                            "area": "área funcional",
                            "modality": "modalidad",
                            "seniority": "nivel de experiencia",
                            "location": "ubicación"
                        }
                        slot_label_next = slot_labels_next.get(nxt, nxt)
                        message += f"¿Quieres agregar más información sobre la {slot_label_next} o buscar empleos ahora?"
                    else:
                        message += "¿Quieres buscar empleos ahora o agregar más criterios?"
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (slot_change_complete): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type": "slot_change_complete", 
                    "message": message, 
                    "slot": slot_to_change,
                    "filled": filtered_state
                })
            else:
                # Si no hay valor nuevo, preguntar por el nuevo valor y guardar que estamos cambiando este slot
                slot_labels = {
                    "industry": "industria",
                    "area": "área funcional",
                    "modality": "modalidad",
                    "seniority": "nivel de experiencia",
                    "location": "ubicación"
                }
                slot_label = slot_labels.get(slot_to_change, slot_to_change)
                conv.state["changing_slot"] = slot_to_change  # Marcar que estamos cambiando este slot
                conv.save()
                message = f"¡Por supuesto! 👌 ¿Qué {slot_label} te gustaría tener? Puedes decirme algo como '{question_for(slot_to_change)}'"
            
                conv.history.append({"role":"system","text": message})
                conv.save()
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (slot_change): {filtered_state}")
                
                return Response({
                    "type": "slot_change", 
                    "message": message, 
                    "slot": slot_to_change,
                    "filled": filtered_state
                })
        
        # Si el usuario quiere ver empleos ahora
        if action_intent and action_intent.get("action") == "show_jobs":
            print("\n✅ Usuario solicita ver empleos explícitamente")
            include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
            results, steps, metadata = decide_jobs(include, exclude, sal_min, currency, topn=3, offset=0, variety=False)
            
            # Si no hay resultados relevantes, informar al usuario
            if not results or not metadata.get("has_relevant_results", True):
                # Analizar alternativas disponibles
                from empleos.engine import analyze_available_alternatives
                analysis = analyze_available_alternatives(include, exclude)
                
                # Construir mensaje informativo sobre qué filtros no tienen resultados
                message = "😔 No encontré empleos que coincidan exactamente con los criterios que me has dado:\n\n"
                
                # Listar los filtros que se intentaron
                filters_tried = []
                if include.get("industry"):
                    filters_tried.append(f"• **Industria**: {', '.join(include['industry'])}")
                if include.get("area"):
                    filters_tried.append(f"• **Área funcional**: {', '.join(include['area'])}")
                if include.get("modality"):
                    filters_tried.append(f"• **Modalidad**: {', '.join(include['modality'])}")
                if include.get("seniority"):
                    filters_tried.append(f"• **Experiencia**: {', '.join(include['seniority'])}")
                if include.get("location"):
                    filters_tried.append(f"• **Ubicación**: {', '.join(include['location'])}")
                if include.get("transport"):
                    filters_tried.append(f"• **Transporte**: Sí")
                if include.get("accessibility"):
                    filters_tried.append(f"• **Accesibilidad**: Sí")
                
                if filters_tried:
                    message += "\n".join(filters_tried)
                
                # Agregar sugerencias específicas basadas en alternativas disponibles
                if analysis.get("suggestions"):
                    message += "\n\n" + "\n".join(analysis["suggestions"])
                
                # Agregar instrucciones sobre cómo cambiar slots
                message += "\n\n🔄 **Para cambiar un criterio específico, puedes decirme:**\n"
                message += "• 'cambiar industria' o 'cambiar industria a [nombre]'\n"
                message += "• 'cambiar área' o 'cambiar área a [nombre]'\n"
                message += "• 'cambiar modalidad' o 'cambiar modalidad a [nombre]'\n"
                message += "• 'cambiar ubicación' o 'cambiar experiencia'\n"
                message += "• O simplemente dime el nuevo valor que quieres (ej: 'tecnología' para cambiar la industria)"
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (no_results): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type":"no_results", 
                    "message": message, 
                    "filled": filtered_state,
                    "alternatives": analysis.get("alternatives", []),
                    "suggestions": analysis.get("suggestions", [])
                })
            
            # Si hay resultados pero se relajaron algunos filtros, informar al usuario
            relaxed_filters = metadata.get("relaxed_filters", [])
            if relaxed_filters:
                relaxed_names = {
                    "industry": "industria",
                    "area": "área funcional",
                    "modality": "modalidad",
                    "seniority": "nivel de experiencia",
                    "location": "ubicación",
                    "transport": "transporte",
                    "accessibility": "accesibilidad"
                }
                relaxed_display = [relaxed_names.get(f, f) for f in relaxed_filters]
                if relaxed_display:
                    print(f"   ⚠️  Se relajaron algunos filtros: {relaxed_display}")
            
            # Obtener información de paginación
            pagination_info = get_job_pagination_info(include, exclude, sal_min, currency)
            
            # Guardar resultados en el estado para selección posterior
            conv.state["last_results"] = _serialize_job_results(results)
            conv.state["current_offset"] = 3  # Preparar para la próxima búsqueda
            conv.save()
            
            # Mensaje con información de paginación
            message = "🎯 Te recomiendo estos empleos:"
            if encouraging_response:
                message = f"{encouraging_response}\n\n{message}"
            
            if relaxed_filters:
                relaxed_names = {
                    "industry": "industria",
                    "area": "área funcional",
                    "modality": "modalidad",
                    "seniority": "nivel de experiencia",
                    "location": "ubicación",
                    "transport": "transporte",
                    "accessibility": "accesibilidad"
                }
                relaxed_display = [relaxed_names.get(f, f) for f in relaxed_filters]
                if relaxed_display:
                    message += f"\n\nℹ️ *Nota: He ajustado algunos filtros ({', '.join(relaxed_display)}) para encontrar empleos relevantes.*"
            
            if pagination_info["has_more"]:
                message += f"\n\n💡 Si quieres ver más empleos, solo escribe 'más empleos' o 'muéstrame más'. Tengo {pagination_info['total_jobs']} empleos disponibles para ti."
            
            # Filtrar solo los slots principales para el frontend
            filtered_state = _get_filtered_state_for_frontend(conv.state)
            print(f"📤 Enviando estado actualizado (show_jobs): {filtered_state}")
            
            reply = {
                "type": "results", 
                "results": results, 
                "trace": steps,
                "pagination_info": pagination_info,
                "message": message,
                "filled": filtered_state
            }
            conv.history.append({"role":"system","text": message})
            conv.save()
            return Response(reply)

        # Si el usuario está pidiendo más empleos
        if action_intent and action_intent.get("action") == "more_jobs":
            # Obtener información de paginación
            include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
            pagination_info = get_job_pagination_info(include, exclude, sal_min, currency)
            
            # Obtener el offset actual (si existe, usar el siguiente, si no, empezar desde 0)
            # Si no hay last_results, significa que es la primera búsqueda, empezar desde 0
            # Si hay last_results, significa que ya se mostraron resultados, usar el offset guardado
            if "last_results" not in conv.state or not conv.state.get("last_results"):
                # Primera búsqueda, empezar desde 0
                current_offset = 0
            else:
                # Ya hay resultados previos, usar el offset guardado
                current_offset = conv.state.get("current_offset", 3)
            
            variety = action_intent.get("variety", False)
            
            print(f"🔍 Búsqueda de más empleos:")
            print(f"   - Offset actual: {current_offset}")
            print(f"   - Variety: {variety}")
            print(f"   - Filtros: {include}")
            
            # Buscar más empleos con paginación
            results, steps, metadata = decide_jobs(include, exclude, sal_min, currency, topn=3, offset=current_offset, variety=variety)
            
            # Si no hay más resultados relevantes, informar al usuario
            if not results or not metadata.get("has_relevant_results", True):
                message = "😔 No hay más empleos que coincidan con tus criterios actuales."
                message += "\n\n💡 Puedes ajustar algunos filtros o cambiar algunos criterios. ¿Qué te gustaría modificar?"
                
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type": "no_more_results",
                    "message": message,
                    "filled": filtered_state
                })
            
            if results:
                # Actualizar offset para la próxima búsqueda (incrementar por el número de resultados mostrados)
                conv.state["current_offset"] = current_offset + len(results)
                conv.state["last_results"] = _serialize_job_results(results)
                conv.save()
                
                # Mensaje de respuesta
                if variety:
                    message = "¡Perfecto! Te muestro empleos diferentes para que tengas más opciones: 🎯"
                else:
                    message = f"¡Aquí tienes {len(results)} empleos más que podrían interesarte: 📋"
                
                # Agregar mensaje si hay más disponibles
                remaining = pagination_info["total_jobs"] - conv.state["current_offset"]
                if remaining > 0:
                    message += f"\n\n💡 Tengo {remaining} empleos más disponibles. Di 'buscar' o 'más empleos' para ver más."
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (more_jobs): {filtered_state}")
                print(f"   - Nuevo offset: {conv.state['current_offset']}")
                print(f"   - Resultados mostrados: {len(results)}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type":"results",
                    "results": results,
                    "trace": steps,
                    "filled": filtered_state,
                    "pagination_info": pagination_info,
                    "current_offset": conv.state["current_offset"],
                    "message": message
                })
            else:
                # No hay más empleos disponibles
                message = "Lo siento, no tengo más empleos que mostrarte con esos criterios. ¿Te gustaría que ajuste los filtros o busque en otras categorías? 🔍"
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (no_more_results): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type": "no_more_results",
                    "message": message,
                    "filled": filtered_state
                })

        # Si el usuario está seleccionando un empleo específico
        if action_intent and action_intent.get("action") == "select_job":
            # Buscar el empleo en los resultados anteriores
            selected_index = action_intent.get("selected_job_index", 0)
            
            # Obtener los últimos resultados de la conversación
            last_results = conv.state.get("last_results", [])
            if last_results and 0 <= selected_index < len(last_results):
                selected_job = last_results[selected_index]
                job_id = selected_job.get("id")
                
                if job_id:
                    # Obtener información completa del empleo desde la BD
                    try:
                        job_full = JobPosting.objects.select_related('company', 'location', 'source').prefetch_related('job_benefits__benefit', 'job_tags__tag').get(id=job_id)
                        
                        # Obtener beneficios
                        benefits = [jb.benefit.name for jb in job_full.job_benefits.all()]
                        
                        # Obtener tags
                        accessibility_tags = [jt.tag.name for jt in job_full.job_tags.filter(kind='accessibility')]
                        transport_tags = [jt.tag.name for jt in job_full.job_tags.filter(kind='transport')]
                        
                        # Construir objeto completo con toda la información
                        full_job_data = {
                            "id": job_full.id,
                            "title": job_full.title,
                            "company": {
                                "name": job_full.company.name,
                                "verified": job_full.company.verified,
                                "rating": float(job_full.company.rating) if job_full.company.rating else None
                            },
                            "location": {
                                "raw_text": job_full.location.raw_text if job_full.location else None
                            },
                            "source": {
                                "name": job_full.source.name,
                                "url": job_full.url
                            },
                            "description": job_full.description,
                            "work_modality": job_full.work_modality,
                            "contract_type": job_full.contract_type,
                            "workday": job_full.workday,
                            "salary_text": job_full.salary_text,
                            "area": job_full.area,
                            "subarea": job_full.subarea,
                            "min_experience": job_full.min_experience,
                            "min_education": job_full.min_education,
                            "published_date": job_full.published_date.isoformat() if job_full.published_date else None,
                            "accessibility_mentioned": job_full.accessibility_mentioned,
                            "transport_mentioned": job_full.transport_mentioned,
                            "disability_friendly": job_full.disability_friendly,
                            "multiple_vacancies": job_full.multiple_vacancies,
                            "benefits": benefits,
                            "accessibility_tags": accessibility_tags,
                            "transport_tags": transport_tags,
                            "url": job_full.url,
                            "created_at": job_full.created_at.isoformat() if job_full.created_at else None,
                        }
                    except JobPosting.DoesNotExist:
                        # Fallback a datos del selected_job si no se encuentra en BD
                        full_job_data = selected_job
                        print(f"⚠️ Empleo {job_id} no encontrado en BD, usando datos de resultados")
                    
                    # Construir respuesta simple para el chat (se mostrará el modal aparte)
                    job_details_response = f"¡Excelente elección! 🎯 Aquí tienes todos los detalles del empleo que seleccionaste."
                    
                    # Filtrar solo los slots principales para el frontend
                    filtered_state = _get_filtered_state_for_frontend(conv.state)
                    print(f"📤 Enviando estado actualizado (job_details): {filtered_state}")
                    
                    conv.history.append({"role":"system","text": job_details_response})
                    conv.save()
                    return Response({
                        "type": "job_details", 
                        "message": job_details_response,
                        "job_id": job_id,
                        "job_data": full_job_data,
                        "filled": filtered_state
                    })
                else:
                    # Filtrar solo los slots principales para el frontend
                    filtered_state = _get_filtered_state_for_frontend(conv.state)
                    conv.history.append({"role":"system","text": "Lo siento, no pude encontrar los detalles completos de ese empleo. ¿Podrías intentar seleccionar otro?"})
                    conv.save()
                    return Response({
                        "type": "error", 
                        "message": "No se pudieron obtener los detalles del empleo",
                        "filled": filtered_state
                    })
            else:
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                conv.history.append({"role":"system","text": "No tengo empleos disponibles para seleccionar. Primero necesito mostrarte algunas opciones. ¿Quieres que busque empleos para ti?"})
                conv.save()
                return Response({
                    "type": "error", 
                    "message": "No hay empleos disponibles para seleccionar",
                    "filled": filtered_state
                })

        # Si faltan slots, pregunta el siguiente
        nxt = next_missing_slot(conv.state)
        if nxt:
            # Contar solo los slots principales que están llenos
            main_slots = ["industry", "area", "modality", "seniority", "location"]
            filled_main_slots = sum(1 for k in main_slots if conv.state.get(k) and conv.state.get(k) not in (None, "", []))
            
            # Si ya tenemos información suficiente (al menos 2 campos principales), ofrecer mostrar empleos
            if filled_main_slots >= 2:
                q = question_for(nxt)
                
                # Construir mensaje con respuesta empática y opción de mostrar empleos
                message = q
                if encouraging_response:
                    message = f"{encouraging_response}\n\n{q}"
                
                # Mensaje más claro con opciones
                message += "\n\n💡 **O si prefieres, puedo mostrarte empleos ahora con la información que ya tengo.** Solo di 'muéstrame empleos' o 'buscar' para ver los resultados."
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (question con can_show_jobs): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type":"question", 
                    "message": message, 
                    "filled": filtered_state, 
                    "can_show_jobs": True
                })
            else:
                q = question_for(nxt)
                
                # Construir mensaje con respuesta empática si la hay
                message = q
                if encouraging_response:
                    message = f"{encouraging_response}\n\n{q}"
                
                # Filtrar solo los slots principales para el frontend
                filtered_state = _get_filtered_state_for_frontend(conv.state)
                print(f"📤 Enviando estado actualizado (question): {filtered_state}")
                
                conv.history.append({"role":"system","text": message})
                conv.save()
                return Response({
                    "type":"question", 
                    "message": message, 
                    "filled": filtered_state
                })

        # Si no faltan slots, devuelve recomendaciones
        print("\n✅ Todos los slots completos, generando recomendaciones")
        include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
        results, steps, metadata = decide_jobs(include, exclude, sal_min, currency, topn=3, offset=0, variety=False)
        
        # Si no hay resultados relevantes, informar al usuario
        if not results or not metadata.get("has_relevant_results", True):
            # Analizar alternativas disponibles
            from empleos.engine import analyze_available_alternatives
            analysis = analyze_available_alternatives(include, exclude)
            
            # Construir mensaje informativo sobre qué filtros no tienen resultados
            message = "😔 No encontré empleos que coincidan exactamente con los criterios que me has dado:\n\n"
            
            # Listar los filtros que se intentaron
            filters_tried = []
            if include.get("industry"):
                filters_tried.append(f"• **Industria**: {', '.join(include['industry'])}")
            if include.get("area"):
                filters_tried.append(f"• **Área funcional**: {', '.join(include['area'])}")
            if include.get("modality"):
                filters_tried.append(f"• **Modalidad**: {', '.join(include['modality'])}")
            if include.get("seniority"):
                filters_tried.append(f"• **Experiencia**: {', '.join(include['seniority'])}")
            if include.get("location"):
                filters_tried.append(f"• **Ubicación**: {', '.join(include['location'])}")
            if include.get("transport"):
                filters_tried.append(f"• **Transporte**: Sí")
            if include.get("accessibility"):
                filters_tried.append(f"• **Accesibilidad**: Sí")
            
            if filters_tried:
                message += "\n".join(filters_tried)
            
            # Agregar sugerencias específicas basadas en alternativas disponibles
            if analysis.get("suggestions"):
                message += "\n\n" + "\n".join(analysis["suggestions"])
            
            # Agregar instrucciones sobre cómo cambiar slots
            message += "\n\n🔄 **Para cambiar un criterio específico, puedes decirme:**\n"
            message += "• 'cambiar industria' o 'cambiar industria a [nombre]'\n"
            message += "• 'cambiar área' o 'cambiar área a [nombre]'\n"
            message += "• 'cambiar modalidad' o 'cambiar modalidad a [nombre]'\n"
            message += "• 'cambiar ubicación' o 'cambiar experiencia'\n"
            message += "• O simplemente dime el nuevo valor que quieres (ej: 'tecnología' para cambiar la industria)"
            
            # Filtrar solo los slots principales para el frontend
            filtered_state = _get_filtered_state_for_frontend(conv.state)
            print(f"📤 Enviando estado actualizado (no_results): {filtered_state}")
            
            conv.history.append({"role":"system","text": message})
            conv.save()
            return Response({
                "type":"no_results", 
                "message": message, 
                "filled": filtered_state,
                "alternatives": analysis.get("alternatives", []),
                "suggestions": analysis.get("suggestions", [])
            })
        
        # Si hay resultados pero se relajaron algunos filtros, informar al usuario
        relaxed_filters = metadata.get("relaxed_filters", [])
        if relaxed_filters:
            relaxed_names = {
                "industry": "industria",
                "area": "área funcional",
                "modality": "modalidad",
                "seniority": "nivel de experiencia",
                "location": "ubicación",
                "transport": "transporte",
                "accessibility": "accesibilidad"
            }
            relaxed_display = [relaxed_names.get(f, f) for f in relaxed_filters]
            if relaxed_display:
                print(f"   ⚠️  Se relajaron algunos filtros: {relaxed_display}")
        
        # Obtener información de paginación
        pagination_info = get_job_pagination_info(include, exclude, sal_min, currency)
        
        # Guardar resultados en el estado para selección posterior
        conv.state["last_results"] = _serialize_job_results(results)
        conv.state["current_offset"] = len(results)  # Preparar para la próxima búsqueda (usar el número de resultados mostrados)
        conv.save()
        
        # Mensaje final empático
        final_message = f"🎯 Te encontré {len(results)} empleos que coinciden con tus criterios:"
        if encouraging_response:
            final_message = f"{encouraging_response}\n\n{final_message}"
        
        if relaxed_filters:
            relaxed_names = {
                "industry": "industria",
                "area": "área funcional",
                "modality": "modalidad",
                "seniority": "nivel de experiencia",
                "location": "ubicación",
                "transport": "transporte",
                "accessibility": "accesibilidad"
            }
            relaxed_display = [relaxed_names.get(f, f) for f in relaxed_filters]
            if relaxed_display:
                final_message += f"\n\nℹ️ *Nota: He ajustado algunos filtros ({', '.join(relaxed_display)}) para encontrar empleos relevantes.*"
        
        remaining = pagination_info["total_jobs"] - len(results)
        if remaining > 0:
            final_message += f"\n\n💡 Tengo {remaining} empleos más disponibles con estos criterios. Di 'buscar' o 'más empleos' para ver más opciones."
        
        # Filtrar solo los slots principales para el frontend
        filtered_state = _get_filtered_state_for_frontend(conv.state)
        print(f"📤 Enviando estado actualizado (results final): {filtered_state}")
        
        conv.history.append({"role":"system","text": final_message})
        conv.save()
        return Response({
            "type":"results", 
            "results": results, 
            "trace": steps, 
            "filled": filtered_state,
            "pagination_info": pagination_info,
            "message": final_message
        })


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


def _field_names(model):
    names = set()
    for f in model._meta.get_fields():
        if getattr(f, "auto_created", False) and not getattr(f, "concrete", False):
            continue
        if getattr(f, "many_to_many", False):
            continue
        if hasattr(f, "editable") and f.editable:
            names.add(f.name)
    return names


def _choices_from_model(model):
    out = {}
    for f in model._meta.fields:
        if f.choices:
            out[f.name] = [label for value, label in f.choices]
    return out


def _fallback_choices():
    return {
        "modality": ["Remoto", "Híbrido", "Presencial"],
        "seniority": ["Junior", "Semi", "Senior"],
        "currency": ["USD", "CLP"],
        "schedule": ["Completa", "Parcial"],
    }


class JobPostingChoicesAPI(APIView):
    def get(self, request):
        choices = _choices_from_model(JobPosting)
        if not choices:
            choices = _fallback_choices()
        else:
            for k, v in _fallback_choices().items():
                choices.setdefault(k, v)
        return Response({"choices": choices}, status=status.HTTP_200_OK)


class JobPostingListCreateAPI(APIView):
    def get(self, request):
        qs = JobPosting.objects.all().order_by("-id")[:200]
        data = []
        for j in qs:
            data.append({
                "id": j.id,
                "title": getattr(j, "title", ""),
                "company": getattr(j.company, "name", None) if getattr(j, "company", None) else None,
                "source": getattr(j.source, "name", None) if getattr(j, "source", None) else None,
                "location": getattr(j.location, "raw_text", None) if getattr(j, "location", None) else None,
                "url": getattr(j, "url", None),
            })
        return Response({"results": data}, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        payload = request.data

        # ---- Campos "amigables" para FKs / M2M
        source_name   = payload.pop("source_name", None)
        company_name  = payload.pop("company_name", None)
        country       = payload.pop("country", None)
        city          = payload.pop("city", None)
        location_text = payload.pop("location_text", None) or payload.pop("location_raw_text", None)
        benefits_in   = payload.pop("benefits", None)  # lista de strings

        # ---- Source
        source = None
        if source_name:
            source, _ = Source.objects.get_or_create(name=source_name)

        # ---- Company
        company = None
        if company_name:
            company, _ = Company.objects.get_or_create(name=company_name)

        # ---- Location (tolerante a esquema)
        location = None
        loc_fields = _field_names(Location)  # nombres de campos editables existentes
        # Construye kwargs solo con campos que EXISTEN realmente
        loc_kwargs = {}
        if "country" in loc_fields and country:
            loc_kwargs["country"] = country
        if "city" in loc_fields and city:
            loc_kwargs["city"] = city

        # Si el modelo SOLO tiene raw_text (como indica tu error)
        if "raw_text" in loc_fields and not loc_kwargs:
            # Si no mandan location_text, arma uno con lo que haya
            raw = location_text or ", ".join([x for x in [city, country] if x]) or "Chile"
            location, _ = Location.objects.get_or_create(raw_text=raw)
        else:
            # El modelo sí tiene city/country u otros; usa get_or_create con defaults
            defaults = {}
            if "raw_text" in loc_fields and location_text:
                defaults["raw_text"] = location_text
            if loc_kwargs:
                location, created = Location.objects.get_or_create(**loc_kwargs, defaults=defaults)
                # Si ya existía pero mandaron raw_text, intenta actualizarlo
                if not created and "raw_text" in loc_fields and location_text and getattr(location, "raw_text", None) != location_text:
                    location.raw_text = location_text
                    location.save(update_fields=["raw_text"])
            elif "raw_text" in loc_fields:
                # último fallback
                raw = location_text or ", ".join([x for x in [city, country] if x]) or "Chile"
                location, _ = Location.objects.get_or_create(raw_text=raw)
            else:
                # si el modelo tuviera otros campos obligatorios, podrías manejar aquí
                pass

        # ---- Campos propios de JobPosting
        allowed = _field_names(JobPosting)
        job_data = {k: v for k, v in payload.items() if k in allowed}

        # Casteos útiles
        for k in ("salary_min", "salary_max"):
            if k in job_data and job_data[k] in ("", None):
                job_data.pop(k)
            elif k in job_data:
                try:
                    job_data[k] = int(job_data[k])
                except Exception:
                    pass  # deja que el modelo/DB valide

        # Inyecta FKs
        if "source" in allowed and source:
            job_data["source"] = source
        if "company" in allowed and company:
            job_data["company"] = company
        if "location" in allowed and location:
            job_data["location"] = location

        # Crea el JobPosting
        try:
            job = JobPosting.objects.create(**job_data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # ---- Beneficios (M2M directa o tabla intermedia)
        if benefits_in:
            if isinstance(benefits_in, str):
                benefits_in = [x.strip() for x in benefits_in.split(",") if x.strip()]
            for b in benefits_in:
                benefit, _ = Benefit.objects.get_or_create(name=b)
                added = False
                if hasattr(job, "benefits") and hasattr(job.benefits, "add"):
                    job.benefits.add(benefit)
                    added = True
                if not added:
                    try:
                        from .models import JobBenefit
                        JobBenefit.objects.get_or_create(job=job, benefit=benefit)
                    except Exception:
                        pass

        return Response(
            {"id": job.id, "message": "JobPosting creado correctamente"},
            status=status.HTTP_201_CREATED
        )