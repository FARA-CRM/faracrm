import { useState } from 'react';
import { Kanban } from '@/components/Kanban';
import { FunnelSelect } from '@/components/FunnelSelect/FunnelSelect';
import { FilterExpression } from '@/services/api/crudTypes';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';

export function ViewKanbanLeads() {
  // Воронка: в канбане показываем лиды и колонки-стадии только выбранной
  // воронки. Пока воронка одна — переключателя нет и фильтра тоже (как
  // раньше, одна доска).
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const leadFilter: FilterExpression | undefined = funnelId
    ? [['funnel_id', '=', funnelId]]
    : undefined;
  const stageFilter: FilterExpression = funnelId
    ? [
        ['active', '=', true],
        ['funnel_id', '=', funnelId],
      ]
    : [['active', '=', true]];

  // Содержимое карточки (прогресс, партнёр, ответственный, дата создания) —
  // расширение extensions/KanbanCardLead; здесь только заголовок и стадии.
  return (
    <Kanban<LeadRecord>
      model="leads"
      groupByField="stage_id"
      groupByModel="lead_stage"
      groupByFilter={stageFilter}
      filter={leadFilter}
      headerExtra={
        <FunnelSelect
          model="lead_funnel"
          value={funnelId}
          onChange={setFunnelId}
        />
      }
    />
  );
}

export function ViewKanbanLeadStage() {
  return (
    <Kanban<LeadStageRecord>
      model="lead_stage"
      fields={['id', 'name', 'funnel_id']}
    />
  );
}

export function ViewKanbanTeamCrm() {
  return <Kanban<TeamCrmRecord> model="team_crm" fields={['id', 'name']} />;
}
