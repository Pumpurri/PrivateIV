from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0014_holdingsnapshot_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolio',
            name='base_currency',
            field=models.CharField(default='PEN', help_text='ISO 4217 currency code used as the base for valuation (e.g., PEN, USD)', max_length=3),
        ),
        migrations.CreateModel(
            name='FXRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('base_currency', models.CharField(help_text='ISO 4217 base currency code (e.g., PEN)', max_length=3)),
                ('quote_currency', models.CharField(help_text='ISO 4217 quote currency code (e.g., USD)', max_length=3)),
                ('rate', models.DecimalField(decimal_places=6, help_text='How many base currency units per 1 quote currency unit', max_digits=16)),
                ('rate_type', models.CharField(choices=[('compra', 'compra'), ('venta', 'venta'), ('mid', 'mid')], default='compra', max_length=10)),
                ('session', models.CharField(choices=[('intraday', 'intraday'), ('cierre', 'cierre')], default='cierre', max_length=10)),
                ('provider', models.CharField(blank=True, default='', help_text='Data provider name (e.g., BCRP)', max_length=50)),
                ('source_series', models.CharField(blank=True, default='', help_text='Provider series code (e.g., PD04645PD)', max_length=20)),
                ('fetched_at', models.DateTimeField(blank=True, help_text='When this rate was fetched from provider', null=True)),
                ('notes', models.CharField(blank=True, default='', help_text='Optional notes', max_length=200)),
            ],
            options={
                'ordering': ['-date', 'base_currency', 'quote_currency'],
            },
        ),
        migrations.AddConstraint(
            model_name='fxrate',
            constraint=models.UniqueConstraint(fields=('date', 'base_currency', 'quote_currency', 'rate_type', 'session'), name='uniq_fxrate_date_pair'),
        ),
        migrations.AddIndex(
            model_name='fxrate',
            index=models.Index(fields=['date'], name='portfolio_fx_date_idx'),
        ),
        migrations.AddIndex(
            model_name='fxrate',
            index=models.Index(fields=['base_currency', 'quote_currency'], name='portfolio_fx_pair_idx'),
        ),
        migrations.AddIndex(
            model_name='fxrate',
            index=models.Index(fields=['rate_type', 'session'], name='portfolio_fx_type_session_idx'),
        ),
    ]

