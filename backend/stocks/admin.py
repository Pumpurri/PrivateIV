from django.contrib import admin
from .models import Stock, StockRefreshStatus

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'company_code', 'is_local', 'currency', 'current_price', 'last_updated')
    list_filter = ('is_local', 'currency')
    search_fields = ('symbol', 'name', 'company_code')


@admin.register(StockRefreshStatus)
class StockRefreshStatusAdmin(admin.ModelAdmin):
    list_display = ('last_refreshed_at',)
