from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from portfolio.models import DailyPortfolioSnapshot, Portfolio, Transaction
from users.models import CustomUser
from users.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


def test_showcase_refuses_non_debug_database():
    with pytest.raises(CommandError, match="DEBUG=True"):
        call_command("create_showcase_portfolio", confirm_disposable=True, stdout=StringIO())


@override_settings(DEBUG=True)
def test_showcase_requires_disposable_confirmation():
    with pytest.raises(CommandError, match="--confirm-disposable"):
        call_command("create_showcase_portfolio", stdout=StringIO())


@override_settings(DEBUG=True)
def test_showcase_refuses_existing_users(monkeypatch):
    user = UserFactory()
    monkeypatch.setenv("SHOWCASE_PASSWORD", "local-test-password")

    with pytest.raises(CommandError, match="not empty"):
        call_command("create_showcase_portfolio", confirm_disposable=True, stdout=StringIO())

    assert CustomUser.objects.filter(pk=user.pk).exists()


@override_settings(DEBUG=True)
def test_showcase_creates_one_populated_portfolio(monkeypatch):
    monkeypatch.setenv("SHOWCASE_PASSWORD", "local-test-password")
    output = StringIO()

    call_command(
        "create_showcase_portfolio",
        confirm_disposable=True,
        days=35,
        transactions=50,
        stdout=output,
    )

    user = CustomUser.objects.get(email="showcase@example.invalid")
    assert user.check_password("local-test-password")
    portfolio = Portfolio.objects.get(user=user)
    assert portfolio.is_default
    assert portfolio.name == "BolsaSim demo"
    assert Transaction.objects.filter(portfolio=portfolio).count() >= 25
    assert DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).count() >= 35
    assert portfolio.performance.time_weighted_return.is_finite()
    assert "Showcase login" in output.getvalue()
    assert "local-test-password" not in output.getvalue()
