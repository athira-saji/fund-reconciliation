from django.urls import path
from reconciliation import views

urlpatterns = [
    path("api/transactions/", views.list_transactions, name="list_transactions"),
    path("api/transactions/upload/", views.upload_csv, name="upload_csv"),
]