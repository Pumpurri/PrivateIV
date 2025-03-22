import os
from celery import Celery
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')

app = Celery('TradeSimulator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
