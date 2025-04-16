from django.contrib import admin
from .models import Portfolio, Holding, Transaction

@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_value', 'cash_balance')
    search_fields = ('user__email',)

@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'stock', 'quantity', 'current_value')
    list_filter = ('stock__symbol',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'transaction_type', 'stock', 'amount', 'timestamp')
    list_filter = ('transaction_type', 'stock__symbol')
    date_hierarchy = 'timestamp'