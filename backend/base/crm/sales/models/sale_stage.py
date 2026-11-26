from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from .sale_funnel import SaleFunnel


async def _default_funnel_id():
    """Воронка по умолчанию — первая по порядку активная."""
    return await env.models.sale_funnel.search_one(
        filter=[("active", "=", True)],
        fields=["id", "name"],
        sort="sequence",
        order="ASC",
    )


class SaleStage(DotModel):
    __table__ = "sale_stage"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Stage Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)
    fold: bool = Boolean(default=False, string="Folded in Kanban")
    color: str = Char(string="Color", default="#3498db")
    # Воронка стадии: канбан показывает только стадии выбранной воронки.
    # default — чтобы стадия, созданная без явной воронки, не повисла вне
    # воронок (иначе лиды/заказы на ней пропадут из канбанов).
    funnel_id: "SaleFunnel | None" = Many2one(
        lambda: env.models.sale_funnel,
        string="Funnel",
        index=True,
        ondelete="restrict",
        default=_default_funnel_id,
    )

    # Прогресс по умолчанию (0–100): заказ получает его при попадании на
    # стадию (StageProgressMixin), дальше правится в заказе руками.
    progress: int = Integer(string="Default progress %", default=0)
    # Выключено → заказам на этой стадии прогресс не проставляется, только руками.
    # default_db: колонка добавляется в старые базы с DEFAULT TRUE, чтобы у
    # уже существующих стадий проставление было включено без миграций.
    progress_auto: bool = Boolean(
        default=True, default_db=True, string="Auto-set progress"
    )


INITIAL_SALE_STAGES = [
    {
        "name": "Черновик",
        "sequence": 10,
        "active": True,
        "fold": False,
        "color": "#6c757d",
        "progress": 10,
    },
    {
        "name": "Отправлено",
        "sequence": 20,
        "active": True,
        "fold": False,
        "color": "#17a2b8",
        "progress": 30,
    },
    {
        "name": "Подтверждено",
        "sequence": 30,
        "active": True,
        "fold": False,
        "color": "#28a745",
        "progress": 60,
    },
    {
        "name": "Выполнено",
        "sequence": 40,
        "active": True,
        "fold": False,
        "color": "#007bff",
        "progress": 100,
    },
    {
        "name": "Отменено",
        "sequence": 50,
        "active": True,
        "fold": True,
        "color": "#dc3545",
        "progress": 0,
    },
]
