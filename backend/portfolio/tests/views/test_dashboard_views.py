from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from portfolio.models import FXRate, Transaction
from portfolio.services import SnapshotService
from portfolio.tests.factories import PortfolioFactory, TransactionFactory
from users.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


class TestPortfolioOverviewView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_overview_uses_portfolio_reporting_currency_by_default(self, set_fx_market_now):
        user = UserFactory.create()
        portfolio = PortfolioFactory(user=user, is_default=False)
        portfolio.reporting_currency = 'USD'
        portfolio.save(update_fields=['reporting_currency'])

        yesterday = date(2026, 4, 16)
        today = date(2026, 4, 17)

        FXRate.objects.create(
            date=yesterday,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=today,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('4.00'),
            rate_type='mid',
            session='cierre',
        )

        set_fx_market_now(yesterday)
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            cash_currency='USD',
        )
        SnapshotService.create_daily_snapshot(portfolio, date=yesterday)

        set_fx_market_now(today)
        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('dashboard-portfolio-overview', kwargs={'portfolio_id': portfolio.id})
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['portfolio']['reporting_currency'] == 'USD'
        assert data['portfolio']['display_currency'] == 'USD'
        assert Decimal(data['portfolio']['total_value']) == Decimal('100.00')
        assert Decimal(data['portfolio']['cash_balance']) == Decimal('100.00')
        assert Decimal(data['portfolio']['day_change_abs']) == Decimal('0.00')
        assert Decimal(data['portfolio']['since_inception_abs']) == Decimal('0.00')
        assert data['snapshots'][0]['display_currency'] == 'USD'
        assert Decimal(data['snapshots'][0]['total_value']) == Decimal('100.00')

    def test_overview_allows_explicit_currency_override(self, set_fx_market_now):
        user = UserFactory.create()
        portfolio = PortfolioFactory(user=user, is_default=False)
        portfolio.reporting_currency = 'USD'
        portfolio.save(update_fields=['reporting_currency'])

        yesterday = date(2026, 4, 16)
        today = date(2026, 4, 17)

        FXRate.objects.create(
            date=yesterday,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('3.50'),
            rate_type='mid',
            session='cierre',
        )
        FXRate.objects.create(
            date=today,
            base_currency='PEN',
            quote_currency='USD',
            rate=Decimal('4.00'),
            rate_type='mid',
            session='cierre',
        )

        set_fx_market_now(yesterday)
        TransactionFactory(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            cash_currency='USD',
        )
        SnapshotService.create_daily_snapshot(portfolio, date=yesterday)

        set_fx_market_now(today)
        self.client.force_authenticate(user=user)
        response = self.client.get(
            reverse('dashboard-portfolio-overview', kwargs={'portfolio_id': portfolio.id}),
            {'currency': 'PEN'},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['portfolio']['display_currency'] == 'PEN'
        assert Decimal(data['portfolio']['total_value']) == Decimal('400.00')
        assert Decimal(data['portfolio']['cash_balance']) == Decimal('400.00')
        assert Decimal(data['portfolio']['day_change_abs']) == Decimal('50.00')
        assert Decimal(data['portfolio']['since_inception_abs']) == Decimal('50.00')
        assert data['snapshots'][0]['display_currency'] == 'PEN'
        assert Decimal(data['snapshots'][0]['total_value']) == Decimal('350.00')
