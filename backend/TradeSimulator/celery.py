import os
from celery import Celery
from TradeSimulator.env import load_optional_dotenv

load_optional_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')

app = Celery('TradeSimulator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
