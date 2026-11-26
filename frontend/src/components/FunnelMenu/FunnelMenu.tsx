import { useEffect, useState } from 'react';
import { Menu } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import { FaraRecord } from '@/services/api/crudTypes';

/**
 * Воронка — настройка вида, поэтому выбор живёт в меню «⋮» (справа от
 * переключателя видов), а не отдельным контролом на доске.
 *
 * useFunnelSelection — состояние выбора на уровень вью: грузит активные
 * воронки и резолвит выбранную (сохранённая в localStorage → текущая →
 * первая). Хук нужен именно вью, а не меню: меню монтируется только при
 * открытии, а фильтр канбана должен примениться сразу при загрузке.
 *
 * FunnelMenu — сами пункты меню: воронки радиокнопками, выбранная с
 * галочкой. Ноль или одна воронка — выбирать нечего, пунктов нет.
 */

const EMPTY: FaraRecord[] = [];

export function useFunnelSelection(model: string) {
  const { data } = useSearchQuery({
    model,
    fields: ['id', 'name'],
    limit: 100,
    sort: 'sequence',
    order: 'asc',
    filter: [['active', '=', true]],
  });
  const funnels = data?.data ?? EMPTY;
  const [value, setValue] = useState<number | null>(null);

  const storageKey = `funnel:${model}`;

  // Выбор: сохранённый (если ещё существует), иначе первая воронка.
  // Одна воронка → фильтр не нужен, снимаем его (null).
  useEffect(() => {
    if (!data) return;
    if (funnels.length < 2) {
      setValue(null);
      return;
    }
    if (value !== null && funnels.some(f => Number(f.id) === value)) return;
    const saved = Number(localStorage.getItem(storageKey));
    const next = funnels.find(f => Number(f.id) === saved) || funnels[0];
    setValue(Number(next.id));
  }, [data, funnels, value, storageKey]);

  const select = (id: number) => {
    localStorage.setItem(storageKey, String(id));
    setValue(id);
  };

  return { funnels, value, select };
}

interface FunnelMenuProps {
  /** Активные воронки (из useFunnelSelection). */
  funnels: FaraRecord[];
  /** Выбранная воронка; null — выбора ещё нет. */
  value: number | null;
  onChange: (id: number) => void;
}

export function FunnelMenu({ funnels, value, onChange }: FunnelMenuProps) {
  const { t } = useTranslation('common');

  if (funnels.length < 2) return null;

  return (
    <>
      <Menu.Label>{t('funnel')}</Menu.Label>
      <Menu.RadioGroup
        value={value === null ? null : String(value)}
        onChange={picked => onChange(Number(picked))}>
        {funnels.map(funnel => (
          <Menu.RadioItem
            key={funnel.id}
            value={String(funnel.id)}
            closeMenuOnClick>
            {String(funnel.name ?? funnel.id)}
          </Menu.RadioItem>
        ))}
      </Menu.RadioGroup>
      <Menu.Divider />
    </>
  );
}
