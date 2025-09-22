from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .nlp import parse_prompt
from .engine import decide_jobs
from .models import Job, Conversation
from django.db import ProgrammingError, OperationalError
from .serializers import ConversationSerializer
from .flow import next_missing_slot, question_for

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
        return list(Job.objects.values_list("role", flat=True).distinct())
    except (ProgrammingError, OperationalError):
        return []

def _merge_state_with_prompt(state: dict, prompt: str):
    """Intenta parsear el texto y completar slots automáticamente."""
    include, exclude, salary_min, currency = parse_prompt(prompt, _roles())
    # map a nuestro state
    if include.get("industry"): state["industry"] = include["industry"][0]
    if include.get("area"):     state["area"] = include["area"][0]
    if include.get("role"):     state["role"] = include["role"][0]
    if include.get("seniority"):state["seniority"] = include["seniority"][0]
    if include.get("modality"): state["modality"] = include["modality"][0]
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
    return include, exclude

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
        conv.history.append({"role":"system","text": q})
        conv.save()
        return Response({"conversation_id": conv.id, "message": q}, status=201)

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
        _merge_state_with_prompt(conv.state, text)

        # Si el usuario pide recomendar ya:
        if any(w in text.lower() for w in ["listo","recomienda","muestrame","sugerencias","ofrecer"]):
            include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
            results, steps = decide_jobs(include, exclude, sal_min, currency, topn=3)
            reply = {"type": "results", "results": results, "trace": steps}
            conv.history.append({"role":"system","text":"Te dejo mis sugerencias"})
            conv.save()
            return Response(reply)

        # Si faltan slots, pregunta el siguiente
        nxt = next_missing_slot(conv.state)
        if nxt:
            q = question_for(nxt)
            conv.history.append({"role":"system","text": q})
            conv.save()
            return Response({"type":"question", "message": q, "filled": conv.state})

        # Si no faltan slots, devuelve recomendaciones
        include, exclude, sal_min, currency = _build_filters_from_state(conv.state)
        results, steps = decide_jobs(include, exclude, sal_min, currency, topn=3)
        conv.history.append({"role":"system","text":"Estas son mis sugerencias"})
        conv.save()
        return Response({"type":"results", "results": results, "trace": steps, "filled": conv.state})