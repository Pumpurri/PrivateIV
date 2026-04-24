from django.db import models


class BenchmarkSeries(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    provider = models.CharField(max_length=32, default='fmp')
    provider_symbol = models.CharField(max_length=32)
    currency = models.CharField(max_length=3, default='USD')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class BenchmarkPrice(models.Model):
    series = models.ForeignKey(
        BenchmarkSeries,
        on_delete=models.CASCADE,
        related_name='prices',
    )
    date = models.DateField(db_index=True)
    close = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['series', 'date'], name='unique_benchmark_series_date'),
        ]
        indexes = [
            models.Index(fields=['date', 'series'], name='benchmark_date_series_idx'),
        ]

    def __str__(self):
        return f"{self.series.code} @ {self.date}: {self.close}"
