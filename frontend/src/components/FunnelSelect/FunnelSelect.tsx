import { useEffect } from 'react';
import { Select } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import { FaraRecord } from '@/services/api/crudTypes';

/**
 * Переключатель воронки в шапке канбана.
 *
 * Классическая CRM: воронок несколько, у каждой свой набор стадий. Канбан
 * показывает только выбранную воронку — компонент держит выбор (в
 * localStorage, чтобы он переживал перезагрузку) и отдаёт id наверх; вью
 * подставляет его в фильтр записей и в фильтр колонок-стадий.
 *
 * Ноль или одна воронка — переключатель не нужен, возвращаем null: для
 * обычной установки «одна воронка» экран не меняется.
 */

const EMPTY: FaraRecord[] = [];

interface FunnelSelectProps {
  /** Модель воронок: `sale_funnel` или `lead_funnel`. */
  model: string;
  /** Выбранная воронка; null — ещё не выбрана. */
  value: number | null;
  onChange: (id: number | null) => void;
}

export function FunnelSelect({ model, value, onChange }: FunnelSelectProps) {
  const { t } = useTranslation('common');
  const { data } = useSearchQuery({
    model,
    fields: ['id', 'name'],
    limit: 100,
    sort: 'sequence',
    order: 'asc',
    filter: [['active', '=', true]],
  });
  const funnels = data?.data ?? EMPTY;

  const storageKey = `funnel:${model}`;

  // Выбор: сохранённый (если ещё существует), иначе первая воронка.
  // Одна воронка → фильтр не нужен, снимаем его (null).
  useEffect(() => {
    if (!data) return;
    if (funnels.length < 2) {
      if (value !== null) onChange(null);
      return;
    }
    if (value !== null && funnels.some(f => Number(f.id) === value)) return;
    const saved = Number(localStorage.getItem(storageKey));
    const next = funnels.find(f => Number(f.id) === saved) || funnels[0];
    onChange(Number(next.id));
  }, [data, funnels, value, onChange, storageKey]);

  if (funnels.length < 2) return null;

  return (
    <Select
      size="xs"
      w={200}
      allowDeselect={false}
      aria-label={t('funnel')}
      data={funnels.map(f => ({
        value: String(f.id),
        label: String(f.name ?? f.id),
      }))}
      value={value === null ? null : String(value)}
      onChange={picked => {
        if (!picked) return;
        const id = Number(picked);
        localStorage.setItem(storageKey, String(id));
        onChange(id);
      }}
    />
  );
}
