"""Общие фикстуры тестов модуля leads."""

import pytest


@pytest.fixture
def sale_name_session(db_pool):
    """Sale._default_name читает sequence через env.apps.db.

    В юнит-окружении сервисы не подняты (env.apps.db — не запущенный сервис),
    поэтому заказ без явного имени не создаётся. Подсовываем пул тестовой БД
    на время теста — так же, как tests.conftest.test_env.
    """
    from backend.base.system.core.enviroment import env
    from backend.base.system.dotorm.dotorm.databases.postgres.session import (
        NoTransactionSession,
    )

    class _Db:
        def get_session(self):
            return NoTransactionSession(db_pool)

    original = env.apps.db
    env.apps.db = _Db()
    try:
        yield
    finally:
        env.apps.db = original
