from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from portfolio.tests.factories import PortfolioFactory
from users.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


def test_stress_seeder_refuses_non_debug_database():
    user = UserFactory()

    with pytest.raises(CommandError, match='DEBUG=True'):
        call_command('create_test_portfolio', username=user.email, confirm_disposable=True, stdout=StringIO())


@override_settings(DEBUG=True)
def test_stress_seeder_requires_disposable_database_acknowledgement():
    with pytest.raises(CommandError, match='--confirm-disposable'):
        call_command('create_test_portfolio', username='unused@example.com', stdout=StringIO())


@override_settings(DEBUG=True)
def test_stress_seeder_does_not_replace_existing_portfolio_by_default():
    user = UserFactory()
    original = PortfolioFactory(user=user, name='UI Stress Portfolio')

    with pytest.raises(CommandError, match='--reset'):
        call_command('create_test_portfolio', username=user.email, confirm_disposable=True, stdout=StringIO())

    original.refresh_from_db()
    assert original.name == 'UI Stress Portfolio'
