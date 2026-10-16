from rest_framework.decorators import api_view
from rest_framework.response import Response
from reconciliation.models import Organization, BankTransaction

@api_view(["GET"])
def list_transactions(request):
    slug = request.headers.get("X-Organization")
    if not slug:
        return Response({"error": "missing header"}, status=400)

    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({"error": "not found"}, status=404)

    transactions = BankTransaction.objects.filter(organization=org).order_by("-date")
    
    data = []
    for t in transactions:
        data.append({
            "id": t.id,
            "date": t.date,
            "description": t.description,
            "amount": str(t.amount),
            "transaction_type": t.transaction_type,
            "bank_reference": t.bank_reference,
            "status": t.status,
        })

    return Response(data, status=200)