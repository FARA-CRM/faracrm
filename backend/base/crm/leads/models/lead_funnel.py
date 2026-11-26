"""Воронки лидов.

Воронка — это свой набор стадий (lead_stage.funnel_id) и свой канбан: лид
всегда лежит в воронке (Lead.funnel_id), поэтому один и тот же экран лидов
показывает стадии и лиды только выбранной воронки. Лиды можно переносить
между воронками — они переезжают на первую стадию новой воронки (за это
отвечает FunnelMixin).

Набор воронок пользователь создаёт сам; при первом запуске модуль заводит
одну «Основную», чтобы поведение «одна воронка как раньше» сохранилось.
"""

from backend.base.system.dotorm.dotorm.fields import Boolean, Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id


class LeadFunnel(DotModel):
    __table__ = "lead_funnel"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Funnel Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)


INITIAL_LEAD_FUNNELS = [
    {"name": "Основная", "sequence": 10, "active": True},
]
