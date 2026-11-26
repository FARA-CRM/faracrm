import { useState } from 'react';
import { Kanban } from '@/components/Kanban';
import { FunnelSelect } from '@/components/FunnelSelect/FunnelSelect';
import { FilterExpression } from '@/services/api/crudTypes';
import type { SaleRecord, SaleStageRecord, TaxRecord } from '@/types/records';

export function ViewKanbanSales() {
  // Воронка: в канбане показываем заказы и колонки-стадии только выбранной
  // воронки. Пока воронка одна — переключателя нет и фильтра тоже (как
  // раньше, одна доска).
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const saleFilter: FilterExpression | undefined = funnelId
    ? [['funnel_id', '=', funnelId]]
    : undefined;
  const stageFilter: FilterExpression = funnelId
    ? [
        ['active', '=', true],
        ['funnel_id', '=', funnelId],
      ]
    : [['active', '=', true]];

  // Содержимое карточки (прогресс, клиент, менеджер, дата заказа) —
  // расширение extensions/KanbanCardSale; здесь только заголовок и стадии.
  return (
    <Kanban<SaleRecord>
      model="sales"
      groupByField="stage_id"
      groupByModel="sale_stage"
      groupByFilter={stageFilter}
      filter={saleFilter}
      headerExtra={
        <FunnelSelect
          model="sale_funnel"
          value={funnelId}
          onChange={setFunnelId}
        />
      }
    />
  );
}

export function ViewKanbanSaleStage() {
  return (
    <Kanban<SaleStageRecord>
      model="sale_stage"
      fields={['id', 'name', 'funnel_id']}
    />
  );
}

export function ViewKanbanTax() {
  return <Kanban<TaxRecord> model="tax" fields={['id', 'name']} />;
}
