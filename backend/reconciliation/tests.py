from decimal import Decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from reconciliation.models import (
    Organization,
    CapitalCall,
    CapitalCallLineItem,
    BankTransaction,
    MatchSuggestion,
    InvestorEntity,
)

class ReconciliationTestSuite(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.org1 = Organization.objects.create(
            name="Northwind",
            slug="northwind"
        )
        self.org2 = Organization.objects.create(
            name="Bluebird",
            slug="bluebird"
        )

        self.call1 = CapitalCall.objects.create(
            organization=self.org1,
            identifier="#1",
            call_date="2026-03-25",
            due_date="2026-04-10",
        )

        self.haller = InvestorEntity.objects.create(
            organization=self.org1,
            name="Haller Capital LLC"
        )
        self.patel = InvestorEntity.objects.create(
            organization=self.org1,
            name="Patel Family Trust"
        )

        self.item1 = CapitalCallLineItem.objects.create(
            organization=self.org1,
            capital_call=self.call1,
            investor_entity=self.haller,
            expected_reference="CC-1001",
            amount_called=Decimal("27500.00"),
            amount_funded=Decimal("0.00"),
            status="open",
        )

        self.item2 = CapitalCallLineItem.objects.create(
            organization=self.org1,
            capital_call=self.call1,
            investor_entity=self.patel,
            expected_reference="CC-1003",
            amount_called=Decimal("12500.00"),
            amount_funded=Decimal("0.00"),
            status="open",
        )

    #1. a missing column rejects the file and saves nothing
    def test_missing_column_rejects_and_saves_nothing(self):
        csv_content = b"Date,Description,Amount\n2026-04-01,Test Wire,1000.00\n"
        f = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        res = self.client.post(
            "/api/transactions/upload/",
            {"file": f},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(BankTransaction.objects.filter(organization=self.org1).count(), 0)

    #2. amount parsing: thousands separators, sign/type mismatches and invalid dates
    def test_amount_and_date_parsing_and_decimal_type(self):
        csv_content = (
            b"Date,Description,Amount,Type,Reference\n"
            b"2026-04-01,Wire In,\"15,000.50\",credit,REF1\n"
            b"bad-date,Wire In,1000.00,credit,REF2\n"
            b"2026-04-02,Debit In,-500.00,credit,REF3\n"
        )
        f = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        res = self.client.post(
            "/api/transactions/upload/",
            {"file": f},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["imported"], 1)
        self.assertEqual(len(data["errors"]), 2)
        txn = BankTransaction.objects.get(bank_reference="REF1")
        self.assertEqual(txn.amount, Decimal("15000.50"))
        self.assertIsInstance(txn.amount, Decimal)

    #3. duplicates: a re-upload and a duplicate inside one file
    def test_duplicates_in_file_and_reupload(self):
        csv_content = (
            b"Date,Description,Amount,Type,Reference\n"
            b"2026-04-01,Wire A,1000.00,credit,DUP1\n"
            b"2026-04-01,Wire A,1000.00,credit,DUP1\n"
        )
        f = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        res1 = self.client.post(
            "/api/transactions/upload/",
            {"file": f},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["imported"], 1)
        self.assertEqual(res1.json()["duplicates"], 1)

        f2 = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        res2 = self.client.post(
            "/api/transactions/upload/",
            {"file": f2},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        self.assertEqual(res2.json()["duplicates"], 2)

    #4. a reference match, including cc1001 and a partial payment
    def test_reference_match_normalized_and_partial(self):
        csv_content = (
            b"Date,Description,Amount,Type,Reference\n"
            b"2026-04-04,Wire cc1001 partial,20000.00,credit,REF_PARTIAL\n"
        )
        f = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        self.client.post(
            "/api/transactions/upload/",
            {"file": f},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        txn = BankTransaction.objects.get(bank_reference="REF_PARTIAL")
        self.assertEqual(txn.status, "suggested")
        match = MatchSuggestion.objects.get(transaction=txn)
        self.assertEqual(match.line_item, self.item1)

    #5. a name and amount match, including candidate collisions
    def test_name_and_amount_match_and_multiple_candidates(self):
        # single candidate match
        csv_single = (
            b"Date,Description,Amount,Type,Reference\n"
            b"2026-04-07,WIRE PATEL FAMILY TRUST,12500.00,credit,REF_NAME_1\n"
        )
        f1 = SimpleUploadedFile("stmt1.csv", csv_single, content_type="text/csv")
        self.client.post(
            "/api/transactions/upload/",
            {"file": f1},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        txn1 = BankTransaction.objects.get(bank_reference="REF_NAME_1")
        self.assertEqual(txn1.status, "suggested")
        self.assertEqual(MatchSuggestion.objects.filter(transaction=txn1).count(), 1)

        # second identical line item for the same investor and amount
        CapitalCallLineItem.objects.create(
            organization=self.org1,
            capital_call=self.call1,
            investor_entity=self.patel,
            expected_reference="CC-1004",
            amount_called=Decimal("12500.00"),
            amount_funded=Decimal("0.00"),
            status="open",
        )

        # ambiguous upload creates 2 suggestions and sets status to needs_review
        csv_ambiguous = (
            b"Date,Description,Amount,Type, Reference\n"
            b"2026-04-08,WIRE PATEL FAMILY TRUST,12500.00,credit,REF_NAME_2\n"
        )
        f2 = SimpleUploadedFile("stmt2.csv", csv_ambiguous, content_type="text/csv")
        self.client.post(
            "/api/transactions/upload/",
            {"file": f2},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        txn2 = BankTransaction.objects.get(bank_reference="REF_NAME_2")
        self.assertEqual(txn2.status, "needs_review")
        self.assertEqual(
            MatchSuggestion.objects.filter(transaction=txn2).count(),
            2,
        )

    #6. an overpayment becomes needs_review with no match
    def test_overpayment_needs_review_no_match(self):
        csv_content = (
            b"Date,Description,Amount,Type,Reference\n"
            b"2026-04-04,Wire CC-1001,35000.00,credit,REF_OVER\n"
        )
        f = SimpleUploadedFile("stmt.csv", csv_content, content_type="text/csv")
        self.client.post(
            "/api/transactions/upload/",
            {"file": f},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        txn = BankTransaction.objects.get(bank_reference="REF_OVER")
        self.assertEqual(txn.status, "needs_review")
        self.assertEqual(MatchSuggestion.objects.filter(transaction=txn).count(), 0)

    #7. approving updates funded amount; a second approval returns 409
    def test_atomic_approval_and_409_prevention(self):
        txn = BankTransaction.objects.create(
            organization=self.org1,
            date="2026-04-04",
            description="Wire CC-1001",
            amount=Decimal("20000.00"),
            transaction_type="credit",
            bank_reference="REF_APP",
            status="suggested",
        )
        m = MatchSuggestion.objects.create(
            transaction=txn,
            line_item=self.item1,
            reason="ref match",
            status="proposed",
        )
        res1 = self.client.post(f"/api/matches/{m.id}/confirm/", HTTP_X_ORGANIZATION="northwind")
        self.assertEqual(res1.status_code, 200)

        self.item1.refresh_from_db()
        self.assertEqual(self.item1.amount_funded, Decimal("20000.00"))

        res2 = self.client.post(f"/api/matches/{m.id}/confirm/", HTTP_X_ORGANIZATION="northwind")
        self.assertEqual(res2.status_code, 409)

        # confirm line item was not funded twice
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.amount_funded, Decimal("20000.00"))

    #8. organization isolation for listing and approving (404)
    def test_organization_isolation_404(self):
        txn = BankTransaction.objects.create(
            organization=self.org1,
            date="2026-04-04",
            description="Wire CC-1001",
            amount=Decimal("20000.00"),
            transaction_type="credit",
            bank_reference="REF_ISO",
            status="suggested",
        )
        m = MatchSuggestion.objects.create(
            transaction=txn,
            line_item=self.item1,

            reason="ref match",
            status="proposed",
        )
        # org2 tries to confirm org1's match
        res = self.client.post(f"/api/matches/{m.id}/confirm/", HTTP_X_ORGANIZATION="bluebird")
        self.assertEqual(res.status_code, 404)

        # org2 listing should see nothing from org1
        res_list = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="bluebird")
        self.assertEqual(len(res_list.json()), 0)