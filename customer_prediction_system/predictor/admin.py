from django.contrib import admin
from .models import Customer, Transaction


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'first_name', 'last_name', 'created_at')
    search_fields = ('customer_id', 'first_name', 'last_name')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'customer', 'amount', 'vendor', 'transaction_type', 'transaction_datetime', 'likelihood_prediction')
    list_filter = ('transaction_type', 'vendor', 'transaction_datetime')
    search_fields = ('transaction_id', 'customer__customer_id', 'customer__first_name', 'customer__last_name', 'vendor')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'transaction_datetime'
    ordering = ('-transaction_datetime',)
