from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0003_alter_stock_current_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='stock',
            name='currency',
            field=models.CharField(default='USD', help_text='ISO 4217 currency code of the stock pricing (e.g., USD, PEN)', max_length=3),
        ),
    ]

