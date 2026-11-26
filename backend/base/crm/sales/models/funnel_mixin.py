"""FunnelMixin — воронка записи и её стадия всегда согласованы.

У стадии есть воронка (stage.funnel_id), у записи (лида/заказа) — своя
(Sale.funnel_id / Lead.funnel_id): по ней фильтруются канбан, список и
отчёты. Два поля не должны разъезжаться, поэтому писать их вразнобой нельзя —
за согласование отвечает одно место (этот миксин):

    пишут стадию  → воронка берётся из стадии;
    пишут воронку → стадия становится первой активной стадией новой воронки
                    (перенос между воронками — это смена воронки);
    пишут обе     → если пара согласована, так и остаётся; если нет,
                    приоритет у воронки (её выбрал пользователь, стадия —
                    устаревшее значение формы).

Пустая воронка (None) при обновлении игнорируется: запись всегда остаётся в
какой-то воронке, иначе она пропадает из канбанов. Очистить можно стадию —
запись остаётся в воронке в колонке «Без стадии».

Использование (у модели должны быть Many2one stage_id и funnel_id, у модели
стадии — Many2one funnel_id; в базовых классах миксин идёт ПЕРЕД
StageProgressMixin, чтобы прогресс брался из уже проставленной стадии):

    class Sale(AuditMixin, FunnelMixin, StageProgressMixin, ...): ...
"""

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod, onchange
from backend.base.system.dotorm.dotorm.model import JsonMode

if TYPE_CHECKING:
    from backend.base.system.dotorm.dotorm.model import DotModel

    _Base = DotModel
else:
    _Base = object


def _relation_ids(record) -> dict:
    """id стадии и воронки из payload или из формы.

    В payload связь — либо число (CRUD-роут, готовые id), либо запись модели
    (код модулей, форма). Нормализует её сам dotorm: сериализация в режиме
    UPDATE отдаёт у Many2one голый FK-id. Незаданные поля не попадают.
    """
    return record.json(
        include={"stage_id", "funnel_id"},
        exclude_unset=True,
        mode=JsonMode.UPDATE,
    )


class FunnelMixin(_Base):
    @classmethod
    def _stage_model(cls):
        return cls.get_fields()["stage_id"].relation_table

    @classmethod
    def _funnel_model(cls):
        return cls.get_fields()["funnel_id"].relation_table

    @classmethod
    async def _stage_funnel_id(cls, stage_id: int | None) -> int | None:
        """Воронка стадии (None — стадия не закреплена за воронкой)."""
        if not stage_id:
            return None
        stage = (
            await cls._stage_model()
            .sudo()
            .search_one(
                filter=[("id", "=", stage_id)], fields=["id", "funnel_id"]
            )
        )
        return stage.funnel_id if stage else None

    @classmethod
    async def _first_stage(cls, funnel_id: int | None):
        """Первая по порядку активная стадия воронки."""
        if not funnel_id:
            return None
        return (
            await cls._stage_model()
            .sudo()
            .search_one(
                filter=[("funnel_id", "=", funnel_id), ("active", "=", True)],
                fields=["id", "name"],
                sort="sequence",
                order="ASC",
            )
        )

    @classmethod
    async def _default_funnel_id(cls) -> int | None:
        """id первой по порядку активной воронки (воронка по умолчанию)."""
        funnel = (
            await cls._funnel_model()
            .sudo()
            .search_one(
                filter=[("active", "=", True)],
                fields=["id"],
                sort="sequence",
                order="ASC",
            )
        )
        return funnel.id if funnel else None

    # ---------- create / update / update_bulk ----------

    @classmethod
    async def _sync_create_funnel(cls, payload) -> None:
        """Новая запись: стадия важнее, воронка — из неё; без стадии —
        первая стадия выбранной (или воронки по умолчанию)."""
        refs = _relation_ids(payload)
        stage_id = refs.get("stage_id")
        funnel_id = refs.get("funnel_id")

        stage_funnel_id = await cls._stage_funnel_id(stage_id)
        if stage_funnel_id:
            payload.funnel_id = stage_funnel_id
            return

        funnel_id = funnel_id or await cls._default_funnel_id()
        if not funnel_id:
            return
        payload.funnel_id = funnel_id

        if not stage_id:
            stage = await cls._first_stage(funnel_id)
            if stage:
                payload.stage_id = stage.id

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None) -> int:
        await self._sync_create_funnel(payload)
        return await super().create(payload, session, depends_jobs)

    async def _sync_update_funnel(self, payload, fields) -> list[str]:
        """Согласовать воронку и стадию при обновлении. Возвращает поля,
        которые реально пойдут в UPDATE (к списку, возможно, добавляются
        stage_id/funnel_id)."""
        cls = self.__class__
        fields = (
            list(fields) if fields is not None else payload.assigned_fields()
        )

        stage_given = "stage_id" in fields
        funnel_given = "funnel_id" in fields
        if not stage_given and not funnel_given:
            return fields

        cur_stage = self.stage_id
        cur_funnel = self.funnel_id
        refs = _relation_ids(payload)
        new_stage = refs.get("stage_id", cur_stage)
        new_funnel = refs.get("funnel_id", cur_funnel)

        # Воронку не очищаем: без неё запись пропадает из канбанов.
        if funnel_given and not new_funnel:
            funnel_given = False
            new_funnel = cur_funnel
            fields = [name for name in fields if name != "funnel_id"]

        stage_changed = new_stage != cur_stage
        funnel_changed = new_funnel != cur_funnel

        if funnel_changed:
            # Стадия подходит новой воронке (форма уже подставила её своим
            # onchange) — оставляем; иначе берём первую стадию воронки.
            stage_funnel = (
                await cls._stage_funnel_id(new_stage)
                if stage_changed
                else None
            )
            if stage_funnel != new_funnel:
                stage = await cls._first_stage(new_funnel)
                new_stage = stage.id if stage else None
        elif stage_changed:
            stage_funnel = await cls._stage_funnel_id(new_stage)
            if stage_funnel:
                new_funnel = stage_funnel

        if not stage_changed and not funnel_changed:
            return fields

        payload.stage_id = new_stage
        if "stage_id" not in fields:
            fields.append("stage_id")
        payload.funnel_id = new_funnel
        if "funnel_id" not in fields:
            fields.append("funnel_id")
        return fields

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        fields = await self._sync_update_funnel(payload, fields)
        return await super().update(payload, fields, session, depends_jobs)

    @hybridmethod
    async def update_bulk(self, ids, payload, session=None, depends_jobs=None):
        """Массовое обновление: payload один на все записи, поэтому
        согласование то же, что при create. Трогаем его только когда в
        payload вообще есть стадия/воронка — иначе массовая правка других
        полей (active и т.п.) переписала бы воронки всем записям."""
        if {"stage_id", "funnel_id"} & set(payload.assigned_fields()):
            await self._sync_create_funnel(payload)
        return await super().update_bulk(ids, payload, session, depends_jobs)

    @onchange("funnel_id")
    async def onchange_funnel_id_stage(self) -> dict:
        """Сменили воронку в форме → сразу показываем её первую стадию."""
        refs = _relation_ids(self)
        funnel_id = refs.get("funnel_id")
        if not funnel_id:
            return {}
        stage_id = refs.get("stage_id")
        if stage_id and await self._stage_funnel_id(stage_id) == funnel_id:
            return {}
        stage = await self._first_stage(funnel_id)
        if not stage:
            return {}
        return {"stage_id": {"id": stage.id, "name": stage.name}}

    @onchange("stage_id")
    async def onchange_stage_id_funnel(self) -> dict:
        """Выбрали стадию другой воронки → подставляем её воронку."""
        refs = _relation_ids(self)
        stage_id = refs.get("stage_id")
        if not stage_id:
            return {}
        funnel_id = await self._stage_funnel_id(stage_id)
        if not funnel_id or funnel_id == refs.get("funnel_id"):
            return {}
        funnel = await self._funnel_model().sudo().get(funnel_id)
        return {"funnel_id": {"id": funnel.id, "name": funnel.name}}
