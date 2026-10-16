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