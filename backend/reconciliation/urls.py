from django.urls import path
from reconciliation import views

urlpatterns = [
    path("api/transactions/", views.list_transactions, name="list_transactions"),
    path("api/transactions/upload/", views.upload_csv, name="upload_csv"),
    path("api/matches/<int:match_id>/confirm/", views.confirm_match, name="confirm_match"),
    path("api/matches/<int:match_id>/reject/", views.reject_match, name="reject_match"),
]