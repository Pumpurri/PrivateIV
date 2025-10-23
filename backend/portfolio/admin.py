from django.contrib import admin
from .models import Portfolio, Holding, Transaction, FXRate

@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('user', 'base_currency', 'total_value', 'cash_balance')
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

@admin.register(FXRate)
class FXRateAdmin(admin.ModelAdmin):
    list_display = ('date', 'quote_currency', 'base_currency', 'rate_type', 'session', 'rate', 'provider', 'source_series', 'fetched_at')
    list_filter = ('base_currency', 'quote_currency', 'rate_type', 'session', 'provider', 'source_series')
    date_hierarchy = 'date'
    search_fields = ('provider', 'source_series', 'notes')
