"""Воронки продаж.

Воронка — это свой набор стадий (sale_stage.funnel_id) и свой канбан: заказ
всегда лежит в воронке (Sale.funnel_id), поэтому один и тот же экран продаж
показывает стадии и заказы только выбранной воронки. Заказы можно переносить
между воронками — они переезжают на первую стадию новой воронки (за это
отвечает FunnelMixin).

Набор воронок пользователь создаёт сам; при первом запуске модуль заводит
одну «Основную», чтобы поведение «одна воронка как раньше» сохранилось.
"""

from backend.base.system.dotorm.dotorm.fields import Boolean, Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id


class SaleFunnel(DotModel):
    __table__ = "sale_funnel"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Funnel Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)


INITIAL_SALE_FUNNELS = [
    {"name": "Основная", "sequence": 10, "active": True},
]
