from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.dotorm.dotorm.access import BYPASS_DOMAIN
from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.sale_stage import SaleStage, INITIAL_SALE_STAGES
from .models.sale_funnel import SaleFunnel, INITIAL_SALE_FUNNELS


class SalesApp(App):
    """
    App for sales management.

    Роли:
    ┌──────────────────────────┬───────────────────────────────────────────┐
    │ Код роли                 │ Описание                                  │
    ├──────────────────────────┼───────────────────────────────────────────┤
    │ sale_user                │ Пользователь — видит только свои заказы   │
    │ sale_manager             │ Менеджер — видит все заказы               │
    │ sale_admin               │ Администратор — полный доступ + настройки │
    └──────────────────────────┴───────────────────────────────────────────┘

    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "sales",
        "name": "Sales",
        "summary": "Module allow work with sales",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        # Sale.partner_id / company_id, SaleLine.product_id, user_id.
        "depends": ["security", "users", "partners", "products", "company"],
    }

    BASE_USER_ACL = {
        "sale_stage": ACL.READ_ONLY,
        "sale_funnel": ACL.READ_ONLY,
        "tax": ACL.READ_ONLY,
        "contract": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        # Пользователь: полный CRUD своих заказов
        "sale_user": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.READ_ONLY,
            "sale_funnel": ACL.READ_ONLY,
            "tax": ACL.READ_ONLY,
            "contract": ACL.READ_ONLY,
        },
        # Менеджер: полный CRUD всех заказов
        "sale_manager": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.READ_ONLY,
            "sale_funnel": ACL.READ_ONLY,
            "tax": ACL.READ_ONLY,
            "contract": ACL.FULL,
        },
        # Администратор: полный доступ + стадии, воронки и налоги
        "sale_admin": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.FULL,
            "sale_funnel": ACL.FULL,
            "tax": ACL.FULL,
            "contract": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        env: "Environment" = app.state.env

        # 1. Роли модуля (иерархия: user → manager → admin) — ДО super():
        #    он создаёт ACL из ROLE_ACL, а роли без строки ACL не достаётся.
        await self._init_sale_roles(env)

        # 2. ACL из BASE_USER_ACL / ROLE_ACL
        await super().post_init(app)

        # 3. Воронки: без них не к чему привязать стадии
        funnel_id = await self._init_sale_funnels(env)

        # 4. Начальные стадии продаж
        await self._init_sale_stages(env, funnel_id)

        # 5. Разовая миграция: старые стадии/заказы — в воронку
        await self._migrate_funnels(env, funnel_id)

        # 6. Row-level rules
        await self._init_sale_rules(env)

    async def _init_sale_funnels(self, env: "Environment") -> int | None:
        """Создаёт воронку по умолчанию; возвращает её id.

        Идемпотентно: если воронки уже есть, возвращает первую активную —
        новые воронки создаёт пользователь.
        """
        existing = await env.models.sale_funnel.search_one(
            filter=[("active", "=", True)],
            fields=["id"],
            sort="sequence",
            order="ASC",
        )
        if existing:
            return existing.id

        for funnel_data in INITIAL_SALE_FUNNELS:
            await env.models.sale_funnel.create(
                payload=SaleFunnel(**funnel_data),
            )

        created = await env.models.sale_funnel.search_one(
            filter=[("active", "=", True)],
            fields=["id"],
            sort="sequence",
            order="ASC",
        )
        return created.id if created else None

    async def _init_sale_stages(
        self, env: "Environment", funnel_id: int | None
    ):
        """Создаёт начальные стадии продаж в воронке по умолчанию."""

        existing = await env.models.sale_stage.search_one(fields=["id"])
        if existing:
            return

        for stage_data in INITIAL_SALE_STAGES:
            payload = SaleStage(**stage_data)
            if funnel_id:
                payload.funnel_id = funnel_id
            await env.models.sale_stage.create(payload=payload)

    async def _migrate_funnels(
        self, env: "Environment", funnel_id: int | None
    ):
        """РАЗОВАЯ МИГРАЦИЯ воронок: старые стадии и заказы → воронка.

        TODO: временный код — нужен только базам, жившим до воронок
        (issue #50): после обновления существующие стадии и заказы должны
        попасть в воронку, иначе они пропадут из канбанов с фильтром по
        воронке. Новые записи воронку получают сами (FunnelMixin) и в
        миграции не нуждаются. Когда основные клиенты обновятся — метод и
        его вызов из post_init удалить.

        Стадии без воронки → воронка по умолчанию; заказы без воронки →
        воронка их стадии, иначе — воронка по умолчанию. Повторный запуск
        ничего не меняет (WHERE funnel_id IS NULL).
        """
        if not funnel_id:
            return

        db = env.models.sale._get_db_session()
        await db.execute(
            "UPDATE sale_stage SET funnel_id = $1 WHERE funnel_id IS NULL",
            [funnel_id],
            cursor="void",
        )
        await db.execute(
            "UPDATE sales s SET funnel_id = st.funnel_id "
            "FROM sale_stage st "
            "WHERE s.stage_id = st.id AND s.funnel_id IS NULL",
            cursor="void",
        )
        await db.execute(
            "UPDATE sales SET funnel_id = $1 WHERE funnel_id IS NULL",
            [funnel_id],
            cursor="void",
        )

    async def _init_sale_roles(self, env: "Environment"):
        """Создаёт роли модуля продаж: user → manager → admin."""
        from backend.base.crm.security.utils import init_module_roles

        await init_module_roles(
            env,
            "sales",
            [
                ("sale_user", "Продажи: пользователь"),
                ("sale_manager", "Продажи: менеджер"),
                ("sale_admin", "Продажи: администратор"),
            ],
        )

    async def _init_sale_rules(self, env: "Environment"):
        """
        Создаёт правила доступа к записям (row-level security).
        """

        from backend.base.crm.security.models.rules import Rule

        # Получаем модели
        sale_model_rec = await env.models.model.search_one(
            filter=[("name", "=", "sale")], fields=["id"]
        )
        sale_line_model_rec = await env.models.model.search_one(
            filter=[("name", "=", "sale_line")], fields=["id"]
        )
        if not sale_model_rec or not sale_line_model_rec:
            return

        # Получаем роли
        role_user = await env.models.role.search_one(
            filter=[("code", "=", "sale_user")], fields=["id"]
        )
        role_manager = await env.models.role.search_one(
            filter=[("code", "=", "sale_manager")], fields=["id"]
        )
        if not role_user or not role_manager:
            return

        rules_to_create = [
            {
                "name": "Заказы на продажу: только свои",
                "model_id": sale_model_rec,
                "role_id": role_user,
                # OR: назначен я, или ответственный не указан
                "domain": [
                    ["user_id", "=", "{{user_id}}"],
                    "or",
                    ["user_id", "=", None],
                ],
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Заказы на продажу: все",
                "model_id": sale_model_rec,
                "role_id": role_manager,
                "domain": BYPASS_DOMAIN,
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Строки заказов: только свои",
                "model_id": sale_line_model_rec,
                "role_id": role_user,
                # Фильтрация через связанное поле sale_id.user_id
                "domain": [
                    ["sale_id.user_id", "=", "{{user_id}}"],
                    "or",
                    ["sale_id.user_id", "=", None],
                ],
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Строки заказов: все",
                "model_id": sale_line_model_rec,
                "role_id": role_manager,
                "domain": BYPASS_DOMAIN,
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
        ]

        for rule_data in rules_to_create:
            existing = await env.models.rule.search_one(
                filter=[("name", "=", rule_data["name"])],
                fields=["id"],
            )
            if existing:
                continue

            await env.models.rule.create(
                payload=Rule(
                    name=rule_data["name"],
                    active=True,
                    model_id=rule_data["model_id"],
                    role_id=rule_data["role_id"],
                    domain=rule_data["domain"],
                    perm_create=rule_data["perm_create"],
                    perm_read=rule_data["perm_read"],
                    perm_update=rule_data["perm_update"],
                    perm_delete=rule_data["perm_delete"],
                )
            )
