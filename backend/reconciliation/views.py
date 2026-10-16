import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from reconciliation.models import (
    BankTransaction,
    CapitalCallLineItem,
    MatchSuggestion,
    Organization,
)

def normalize_reference(text):
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def normalize_name(text):
    cleaned = re.sub(r"[^A-Za-z0-9]", " ", text).upper()
    words = cleaned.split()
    if words and words[-1] in ["LLC", "LP", "LTD", "INC"]:
        words.pop()
    return " ".join(words)


def run_matcher_for_credit(txn):
    #step 1: find eligible line items
    all_line_items = CapitalCallLineItem.objects.filter(
        organization=txn.organization
    )
    eligible = []
    for item in all_line_items:
        has_balance = item.amount_called > item.amount_funded
        date_ok = item.capital_call.call_date <= txn.date
        if has_balance and date_ok:
            eligible.append(item)

    #step 2: reference check
    norm_desc = normalize_reference(txn.description)
    norm_txn_ref = normalize_reference(txn.bank_reference)

    ref_matches = []
    for item in eligible:
        item_ref = normalize_reference(item.expected_reference)
        if item_ref and (item_ref in norm_desc or item_ref in norm_txn_ref):
            ref_matches.append(item)

    if len(ref_matches) == 1:
        candidate = ref_matches[0]
        remaining = candidate.get_remaining_amount()
        if txn.amount <= remaining:
            txn.status = "suggested"
            txn.save(update_fields=["status"])
            MatchSuggestion.objects.create(
                transaction=txn,
                line_item=candidate,
                status="proposed",
                reason=f"Reference {candidate.expected_reference} found; amount {txn.amount} within remaining {remaining}",
            )
            return
        else:
            txn.status = "needs_review"
            txn.save(update_fields=["status"])
            return

    if len(ref_matches) > 1:
        txn.status = "needs_review"
        txn.save(update_fields=["status"])
        for candidate in ref_matches:
            MatchSuggestion.objects.create(
                transaction=txn,
                line_item=candidate,
                status="proposed",
                reason=f"Multiple matching references found; candidate {candidate.expected_reference}",
            )
        return

    #step 3: name and exact amount check if no reference was found
    desc_words = set(re.findall(r"\b[A-Za-z0-9]+\b", txn.description.upper()))
    name_matches = []

    for item in eligible:
        if txn.amount == item.get_remaining_amount():
            norm_investor = normalize_name(item.investor_entity.name)
            inv_words = set(norm_investor.split())
            if inv_words and inv_words.issubset(desc_words):
                name_matches.append(item)

    if len(name_matches) == 1:
        candidate = name_matches[0]
        txn.status = "suggested"
        txn.save(update_fields=["status"])
        MatchSuggestion.objects.create(
            transaction=txn,
            line_item=candidate,
            status="proposed",
            reason=f"Name {candidate.investor_entity.name} and exact remaining amount {txn.amount} matched",
        )
    elif len(name_matches) > 1:
        txn.status = "needs_review"
        txn.save(update_fields=["status"])
        for candidate in name_matches:
            MatchSuggestion.objects.create(
                transaction=txn,
                line_item=candidate,
                status="proposed",
                reason=f"Multiple name candidates with identical amount {txn.amount}",
            )
    else:
        txn.status = "needs_review"
        txn.save(update_fields=["status"])

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
        matches_data = []
        for m in t.matches.all():
            matches_data.append({
                "id": m.id,
                "line_item_id": m.line_item.id,
                "investor_name": m.line_item.investor_entity.name,
                "expected_reference": m.line_item.expected_reference,
                "status": m.status,
                "reason": m.reason,
            })
        data.append({
            "id": t.id,
            "date": str(t.date),
            "description": t.description,
            "amount": str(t.amount),
            "transaction_type": t.transaction_type,
            "bank_reference": t.bank_reference,
            "status": t.status,
            "matches": matches_data,
        })

    return Response(data, status=200)

@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload_csv(request):
    slug = request.headers.get("X-Organization")
    if not slug:
        return Response({"error": "missing header"}, status=400)

    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({"error": "not found"}, status=404)

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return Response({"error": "no file provided"}, status=400)

    #read text lines
    text_data = uploaded_file.read().decode("utf-8-sig")
    lines = [line for line in text_data.splitlines() if line.strip()]
    if not lines:
        return Response({"error": "empty file"}, status=400)

    reader = csv.reader(lines)
    header = [col.strip().lower() for col in next(reader)]

    required = ["date", "description", "amount", "type", "reference"]
    for req in required:
        if req not in header:
            return Response({"error": f"missing column {req}"}, status=400)

    #map column names to index
    d_idx = header.index("date")
    desc_idx = header.index("description")
    amt_idx = header.index("amount")
    type_idx = header.index("type")
    ref_idx = header.index("reference")

    imported_count = 0
    duplicate_count = 0
    errors = []
    seen_refs = set()

    #process row by row
    for line_num, row in enumerate(reader, start=2):
        if len(row) < len(header):
            errors.append({"line": line_num, "message": "missing columns"})
            continue

        raw_date = row[d_idx].strip()
        raw_desc = row[desc_idx].strip()
        raw_amt = row[amt_idx].strip().replace(",", "")
        raw_type = row[type_idx].strip().lower()
        raw_ref = row[ref_idx].strip()

        if not raw_desc or not raw_ref:
            errors.append({"line": line_num, "message": "description and reference are required"})
            continue

        try:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            errors.append({"line": line_num, "message": f"invalid date: {raw_date}"})
            continue

        #check amount
        try:
            amount_val = Decimal(raw_amt)
        except InvalidOperation:
            errors.append({"line": line_num, "message": f"invalid amount: {raw_amt}"})
            continue

        if amount_val == Decimal("0"):
            errors.append({"line": line_num, "message": "amount cannot be zero"})
            continue

        #check type and sign
        if raw_type not in ["credit", "debit"]:
            errors.append({"line": line_num, "message": f"invalid type: {raw_type}"})
            continue
        if raw_type == "credit" and amount_val <= 0:
            errors.append({"line": line_num, "message": "credit must be positive"})
            continue
        if raw_type == "debit" and amount_val >= 0:
            errors.append({"line": line_num, "message": "debit must be negative"})
            continue

        #duplicate check
        already_exists = BankTransaction.objects.filter(
            organization=org, bank_reference=raw_ref
        ).exists()

        if raw_ref in seen_refs or already_exists:
            duplicate_count += 1
            errors.append({"line": line_num, "message": f"duplicate reference: {raw_ref}"})
            continue

        seen_refs.add(raw_ref)

        #save transaction
        if raw_type == "debit":
            BankTransaction.objects.create(
                organization=org,
                date=parsed_date,
                description=raw_desc,
                amount=amount_val,
                transaction_type=raw_type,
                bank_reference=raw_ref,
                status="ignored",
            )
            imported_count += 1
        else:
            txn = BankTransaction.objects.create(
                organization=org,
                date=parsed_date,
                description=raw_desc,
                amount=amount_val,
                transaction_type=raw_type,
                bank_reference=raw_ref,
                status="needs_review",
            )
            run_matcher_for_credit(txn)
            imported_count += 1

    return Response({
        "imported": imported_count,
        "duplicates": duplicate_count,
        "errors": errors,
    }, status=200)