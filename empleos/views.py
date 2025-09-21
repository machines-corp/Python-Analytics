from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .nlp import parse_prompt
from .engine import decide_jobs
from .models import Job

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