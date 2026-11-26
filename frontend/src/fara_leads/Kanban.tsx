import { Kanban } from '@/components/Kanban';
import {
  FunnelMenu,
  useFunnelSelection,
} from '@/components/FunnelMenu/FunnelMenu';
import { FilterExpression } from '@/services/api/crudTypes';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';

export function ViewKanbanLeads() {
  // Воронка: в канбане показываем лиды и колонки-стадии только выбранной
  // воронки. Выбор — в меню вида «⋮». Пока воронка одна — пункта нет и
  // фильтра тоже (как раньше, одна доска).
  const {
    funnels,
    value: funnelId,
    select,
  } = useFunnelSelection('lead_funnel');
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
      menuExtra={
        <FunnelMenu funnels={funnels} value={funnelId} onChange={select} />
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
