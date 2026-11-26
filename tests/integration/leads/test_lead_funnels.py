"""
Integration tests: воронки лидов (issue #50) — несколько воронок со своими
стадиями, перенос лидов между воронками, создание заказа из лида в выбранную
воронку продаж.

Run: pytest tests/integration/leads/test_lead_funnels.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration

from backend.base.crm.leads.models.lead_funnel import LeadFunnel
from backend.base.crm.leads.models.lead_stage import LeadStage
from backend.base.crm.leads.models.leads import Lead
from backend.base.crm.sales.models.sale import Sale
from backend.base.crm.sales.models.sale_funnel import SaleFunnel
from backend.base.crm.sales.models.sale_stage import SaleStage


def _id(value):
    """Many2one после get/search — объект со .id либо голый id."""
    return getattr(value, "id", value)


async def _make_lead_stage(funnel_id: int, name: str, sequence: int) -> int:
    return await LeadStage.create(
        LeadStage(name=name, sequence=sequence, funnel_id=funnel_id)
    )


async def _make_sale_funnel(name: str, stages: list[tuple[str, int]]) -> tuple:
    """Воронка продаж + её стадии → (funnel_id, [stage_ids])."""
    funnel_id = await SaleFunnel.create(SaleFunnel(name=name))
    stage_ids = [
        await SaleStage.create(
            SaleStage(name=stage_name, sequence=sequence, funnel_id=funnel_id)
        )
        for stage_name, sequence in stages
    ]
    return funnel_id, stage_ids


class TestLeadFunnels:
    async def test_lead_funnel_taken_from_stage(self):
        funnel_id = await LeadFunnel.create(LeadFunnel(name="Лиды A"))
        stage_id = await _make_lead_stage(funnel_id, "Новый", 10)

        lead_id = await Lead.create(Lead(name="Лид", stage_id=stage_id))

        lead = await Lead.get(lead_id, fields=["id", "funnel_id", "stage_id"])
        assert _id(lead.funnel_id) == funnel_id
        assert _id(lead.stage_id) == stage_id

    async def test_move_lead_between_funnels(self):
        funnel_a = await LeadFunnel.create(
            LeadFunnel(name="Лиды A", sequence=10)
        )
        stage_a = await _make_lead_stage(funnel_a, "Квалификация", 20)
        funnel_b = await LeadFunnel.create(
            LeadFunnel(name="Лиды B", sequence=20)
        )
        first_stage_b = await _make_lead_stage(funnel_b, "Новый", 10)

        lead_id = await Lead.create(Lead(name="Лид", stage_id=stage_a))

        lead = await Lead.get(lead_id)
        await lead.update(Lead(funnel_id=funnel_b))

        moved = await Lead.get(lead_id, fields=["id", "funnel_id", "stage_id"])
        assert _id(moved.funnel_id) == funnel_b
        assert _id(moved.stage_id) == first_stage_b

    async def test_lead_stages_filtered_by_funnel(self):
        funnel_a = await LeadFunnel.create(
            LeadFunnel(name="Лиды A", sequence=10)
        )
        funnel_b = await LeadFunnel.create(
            LeadFunnel(name="Лиды B", sequence=20)
        )
        await _make_lead_stage(funnel_a, "A1", 10)
        await _make_lead_stage(funnel_b, "B1", 10)

        stages = await LeadStage.search(
            filter=[("funnel_id", "=", funnel_b), ("active", "=", True)],
            fields=["id", "name"],
        )

        assert [s.name for s in stages] == ["B1"]


class TestSaleFromLeadFunnel:
    async def test_create_sale_in_chosen_funnel(self, sale_name_session):
        lead_funnel = await LeadFunnel.create(LeadFunnel(name="Лиды"))
        lead_stage = await _make_lead_stage(lead_funnel, "Новый", 10)
        lead_id = await Lead.create(Lead(name="Заявка", stage_id=lead_stage))

        funnel_a, stages_a = await _make_sale_funnel(
            "Воронка A", [("Черновик", 10)]
        )
        funnel_b, stages_b = await _make_sale_funnel(
            "Воронка B", [("Новый", 10), ("Оплачен", 20)]
        )

        lead = await Lead.get(lead_id)
        sale_id = await lead.create_sale(funnel_id=funnel_b)

        sale = await Sale.search(
            filter=[("id", "=", sale_id)],
            fields=["id", "funnel_id", "stage_id"],
        )
        assert len(sale) == 1
        assert _id(sale[0].funnel_id) == funnel_b
        assert _id(sale[0].stage_id) == stages_b[0]

    async def test_create_sale_keeps_funnel_of_stage(self, sale_name_session):
        lead_funnel = await LeadFunnel.create(LeadFunnel(name="Лиды"))
        lead_stage = await _make_lead_stage(lead_funnel, "Новый", 10)
        lead_id = await Lead.create(Lead(name="Заявка", stage_id=lead_stage))

        funnel_a, stages_a = await _make_sale_funnel(
            "Воронка A", [("Черновик", 10), ("Отправлено", 20)]
        )
        await _make_sale_funnel("Воронка B", [("Новый", 10)])

        lead = await Lead.get(lead_id)
        sale_id = await lead.create_sale()

        sale = await Sale.search(
            filter=[("id", "=", sale_id)],
            fields=["id", "funnel_id", "stage_id"],
        )
        # Без явной воронки берётся первая по порядку активная стадия, а
        # воронка заказа подтягивается из неё — пара всегда согласована.
        assert _id(sale[0].stage_id) == stages_a[0]
        assert _id(sale[0].funnel_id) == funnel_a
