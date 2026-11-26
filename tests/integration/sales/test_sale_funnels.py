"""
Integration tests: воронки продаж (issue #50) — несколько воронок со своими
стадиями, перенос заказов между воронками, создание заказа из лида в
выбранную воронку.

Воронка заказа и воронка его стадии всегда согласованы (FunnelMixin):
сменили воронку → заказ переезжает на первую стадию новой воронки;
сменили стадию на стадию другой воронки → воронка подтягивается.

Run: pytest tests/integration/sales/test_sale_funnels.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration

from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.sales.models.sale import Sale
from backend.base.crm.sales.models.sale_funnel import SaleFunnel
from backend.base.crm.sales.models.sale_stage import SaleStage


def _id(value):
    """Many2one после get/search — объект со .id либо голый id."""
    return getattr(value, "id", value)


async def _make_funnel(name: str, sequence: int = 10) -> int:
    return await SaleFunnel.create(SaleFunnel(name=name, sequence=sequence))


async def _make_stage(funnel_id: int, name: str, sequence: int) -> int:
    return await SaleStage.create(
        SaleStage(name=name, sequence=sequence, funnel_id=funnel_id)
    )


async def _get_sale(sale_id: int):
    return await Sale.get(sale_id, fields=["id", "funnel_id", "stage_id"])


class TestSaleFunnelStages:
    async def test_stage_belongs_to_funnel(self):
        funnel_id = await _make_funnel("Воронка A")
        stage_id = await _make_stage(funnel_id, "Новый", 10)

        stage = await SaleStage.get(stage_id, fields=["id", "funnel_id"])

        assert _id(stage.funnel_id) == funnel_id

    async def test_stages_are_filtered_by_funnel(self):
        """Канбан берёт стадии с фильтром по funnel_id: доски не смешиваются."""
        funnel_a = await _make_funnel("Воронка A", sequence=10)
        funnel_b = await _make_funnel("Воронка B", sequence=20)
        await _make_stage(funnel_a, "A1", 10)
        await _make_stage(funnel_a, "A2", 20)
        await _make_stage(funnel_b, "B1", 10)

        stages = await SaleStage.search(
            filter=[("funnel_id", "=", funnel_b), ("active", "=", True)],
            fields=["id", "name"],
            sort="sequence",
            order="ASC",
        )

        assert [s.name for s in stages] == ["B1"]


class TestSaleFunnelSync:
    async def test_create_takes_funnel_from_stage(self):
        funnel_a = await _make_funnel("Воронка A")
        stage_a = await _make_stage(funnel_a, "Новый", 10)
        partner_id = await Partner.create(Partner(name="Клиент"))

        sale_id = await Sale.create(
            Sale(name="SO-F-1", stage_id=stage_a, partner_id=partner_id)
        )

        sale = await _get_sale(sale_id)
        assert _id(sale.funnel_id) == funnel_a
        assert _id(sale.stage_id) == stage_a

    async def test_create_with_funnel_takes_its_first_stage(self):
        funnel_a = await _make_funnel("Воронка A")
        first_stage = await _make_stage(funnel_a, "Новый", 10)
        await _make_stage(funnel_a, "Оплачен", 20)
        partner_id = await Partner.create(Partner(name="Клиент"))

        sale_id = await Sale.create(
            Sale(name="SO-F-2", funnel_id=funnel_a, partner_id=partner_id)
        )

        sale = await _get_sale(sale_id)
        assert _id(sale.funnel_id) == funnel_a
        assert _id(sale.stage_id) == first_stage

    async def test_create_with_funnel_gets_stage_progress(self):
        """Стадия проставляется воронкой, но прогресс из неё всё равно берётся:
        FunnelMixin идёт перед StageProgressMixin."""
        funnel_a = await _make_funnel("Воронка A")
        stage = await SaleStage.create(
            SaleStage(
                name="В работе",
                sequence=10,
                funnel_id=funnel_a,
                progress=40,
                progress_auto=True,
            )
        )
        partner_id = await Partner.create(Partner(name="Клиент"))

        sale_id = await Sale.create(
            Sale(name="SO-F-P", funnel_id=funnel_a, partner_id=partner_id)
        )

        sale = await Sale.get(sale_id, fields=["id", "stage_id", "progress"])
        assert _id(sale.stage_id) == stage
        assert sale.progress == 40

    async def test_move_funnel_moves_stage_to_new_funnel(self):
        funnel_a = await _make_funnel("Воронка A", sequence=10)
        await _make_stage(funnel_a, "Черновик", 10)
        stage_a2 = await _make_stage(funnel_a, "Отправлено", 20)

        funnel_b = await _make_funnel("Воронка B", sequence=20)
        stage_b1 = await _make_stage(funnel_b, "Новый", 10)
        await _make_stage(funnel_b, "Оплачен", 20)

        partner_id = await Partner.create(Partner(name="Клиент"))
        sale_id = await Sale.create(
            Sale(name="SO-F-3", stage_id=stage_a2, partner_id=partner_id)
        )

        sale = await Sale.get(sale_id)
        await sale.update(Sale(funnel_id=funnel_b))

        moved = await _get_sale(sale_id)
        assert _id(moved.funnel_id) == funnel_b
        # Стадия старой воронки не осталась заказом новой — взята первая.
        assert _id(moved.stage_id) == stage_b1

    async def test_move_stage_to_other_funnel_updates_funnel(self):
        funnel_a = await _make_funnel("Воронка A", sequence=10)
        stage_a = await _make_stage(funnel_a, "Черновик", 10)
        funnel_b = await _make_funnel("Воронка B", sequence=20)
        await _make_stage(funnel_b, "Новый", 10)
        stage_b2 = await _make_stage(funnel_b, "Оплачен", 20)

        partner_id = await Partner.create(Partner(name="Клиент"))
        sale_id = await Sale.create(
            Sale(name="SO-F-4", stage_id=stage_a, partner_id=partner_id)
        )

        sale = await Sale.get(sale_id)
        await sale.update(Sale(stage_id=stage_b2))

        moved = await _get_sale(sale_id)
        assert _id(moved.stage_id) == stage_b2
        assert _id(moved.funnel_id) == funnel_b

    async def test_funnel_is_not_cleared(self):
        funnel_a = await _make_funnel("Воронка A")
        stage_a = await _make_stage(funnel_a, "Новый", 10)
        partner_id = await Partner.create(Partner(name="Клиент"))
        sale_id = await Sale.create(
            Sale(name="SO-F-5", stage_id=stage_a, partner_id=partner_id)
        )

        sale = await Sale.get(sale_id)
        await sale.update(Sale(funnel_id=None))

        # Без воронки заказ пропал бы из канбанов — снятие воронки игнорируем.
        kept = await _get_sale(sale_id)
        assert _id(kept.funnel_id) == funnel_a
        assert _id(kept.stage_id) == stage_a

    async def test_stage_cleared_keeps_funnel(self):
        funnel_a = await _make_funnel("Воронка A")
        stage_a = await _make_stage(funnel_a, "Новый", 10)
        partner_id = await Partner.create(Partner(name="Клиент"))
        sale_id = await Sale.create(
            Sale(name="SO-F-6", stage_id=stage_a, partner_id=partner_id)
        )

        sale = await Sale.get(sale_id)
        await sale.update(Sale(stage_id=None))

        updated = await _get_sale(sale_id)
        assert _id(updated.funnel_id) == funnel_a
        assert _id(updated.stage_id) is None


class TestSaleFunnelBulk:
    async def test_bulk_update_other_field_keeps_funnel(self):
        """Массовая правка не воронки (active) не должна трогать воронки."""
        funnel_a = await _make_funnel("Воронка A", sequence=10)
        stage_a = await _make_stage(funnel_a, "Черновик", 10)
        funnel_b = await _make_funnel("Воронка B", sequence=20)
        stage_b = await _make_stage(funnel_b, "Новый", 10)
        partner_id = await Partner.create(Partner(name="Клиент"))

        sale_a = await Sale.create(
            Sale(name="SO-B-1", stage_id=stage_a, partner_id=partner_id)
        )
        sale_b = await Sale.create(
            Sale(name="SO-B-2", stage_id=stage_b, partner_id=partner_id)
        )

        await Sale.update_bulk([sale_a, sale_b], Sale(active=False))

        sales = await Sale.search(
            filter=[("id", "in", [sale_a, sale_b])],
            fields=["id", "funnel_id", "active"],
        )
        by_id = {s.id: s for s in sales}
        assert by_id[sale_a].active is False
        assert _id(by_id[sale_a].funnel_id) == funnel_a
        assert _id(by_id[sale_b].funnel_id) == funnel_b

    async def test_bulk_update_funnel_moves_stages(self):
        funnel_a = await _make_funnel("Воронка A", sequence=10)
        stage_a1 = await _make_stage(funnel_a, "Черновик", 10)
        await _make_stage(funnel_a, "Отправлено", 20)
        funnel_b = await _make_funnel("Воронка B", sequence=20)
        first_stage_b = await _make_stage(funnel_b, "Новый", 10)
        partner_id = await Partner.create(Partner(name="Клиент"))

        sale_1 = await Sale.create(
            Sale(name="SO-B-3", stage_id=stage_a1, partner_id=partner_id)
        )
        sale_2 = await Sale.create(
            Sale(name="SO-B-4", stage_id=stage_a1, partner_id=partner_id)
        )

        await Sale.update_bulk([sale_1, sale_2], Sale(funnel_id=funnel_b))

        sales = await Sale.search(
            filter=[("id", "in", [sale_1, sale_2])],
            fields=["id", "funnel_id", "stage_id"],
        )
        for sale in sales:
            assert _id(sale.funnel_id) == funnel_b
            assert _id(sale.stage_id) == first_stage_b


class TestSaleFunnelMigration:
    async def test_migrates_legacy_rows_to_funnel(self, db_pool):
        """Апгрейд старой базы: стадии и заказы без воронки получают её при
        post_init (иначе они пропали бы из канбанов с фильтром по воронке)."""
        from backend.base.crm.sales.app import SalesApp
        from backend.base.system.core.enviroment import env

        stage_id = await SaleStage.create(
            SaleStage(name="Старая", sequence=10, funnel_id=None)
        )
        partner_id = await Partner.create(Partner(name="Клиент"))
        sale_id = await Sale.create(
            Sale(name="SO-LEGACY", stage_id=stage_id, partner_id=partner_id)
        )

        # Состояние «до апгрейда»: воронки нигде не проставлены.
        db = env.models.sale._get_db_session()
        await db.execute(
            "UPDATE sales SET funnel_id = NULL WHERE id = $1",
            [sale_id],
            cursor="void",
        )
        await db.execute(
            "UPDATE sale_stage SET funnel_id = NULL WHERE id = $1",
            [stage_id],
            cursor="void",
        )

        app = SalesApp()
        funnel_id = await app._init_sale_funnels(env)
        assert funnel_id
        await app._migrate_funnels(env, funnel_id)

        stage = await SaleStage.get(stage_id, fields=["id", "funnel_id"])
        sale = await _get_sale(sale_id)
        assert _id(stage.funnel_id) == funnel_id
        assert _id(sale.funnel_id) == funnel_id
