from django.db import models
from decimal import Decimal

class Organization(models.Model):
    slug = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class BankTransaction(models.Model):
    TYPE_CHOICES = [
        ('credit', 'credit'),
        ('debit', 'debit'),
    ]

    STATUS_CHOICES = [
        ('suggested', 'suggested'),
        ('needs_review', 'needs_review'),
        ('reconciled', 'reconciled'),
        ('ignored', 'ignored'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    bank_reference = models.CharField(max_length=128)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='needs_review')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'bank_reference'],
                name='unique_org_bank_reference'
            )
        ]

    def __str__(self):
        return f"{self.bank_reference} - {self.amount}"

class InvestorEntity(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='investors')
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} - {self.organization.slug}"

class CapitalCall(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='capital_calls')
    identifier = models.CharField(max_length=64)
    call_date = models.DateField()
    due_date = models.DateField()

    def __str__(self):
        return f"{self.organization.slug} {self.identifier}"

class CapitalCallLineItem(models.Model):
    STATUS_CHOICES = [
        ('open', 'open'),
        ('partially_funded', 'partially_funded'),
        ('funded', 'funded'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='org_line_items')
    capital_call = models.ForeignKey(CapitalCall, on_delete=models.CASCADE, related_name='call_line_items')
    investor_entity = models.ForeignKey(InvestorEntity, on_delete=models.CASCADE, related_name='line_items')
    expected_reference = models.CharField(max_length=64)
    amount_called = models.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='open')

    def get_remaining_amount(self):
        return self.amount_called - self.amount_funded

    def __str__(self):
        return f"{self.expected_reference} - {self.investor_entity.name}"

class MatchSuggestion(models.Model):
    STATUS_CHOICES = [
        ('proposed', 'proposed'),
        ('approved', 'approved'),
        ('rejected', 'rejected'),
    ]

    transaction = models.ForeignKey(BankTransaction, on_delete=models.CASCADE, related_name='matches')
    line_item = models.ForeignKey(CapitalCallLineItem, on_delete=models.CASCADE, related_name='matches')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='proposed')
    reason = models.TextField()

    def __str__(self):
        return f"Match {self.transaction.bank_reference} to {self.line_item.expected_reference} - {self.status}"