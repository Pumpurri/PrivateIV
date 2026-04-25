import os
from celery import Celery
from celery.schedules import crontab
from TradeSimulator.env import load_optional_dotenv

load_optional_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')

app = Celery('TradeSimulator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
