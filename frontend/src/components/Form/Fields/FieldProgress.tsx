import { useState } from 'react';

import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';
import {
  ProgressLine,
  ProgressSlider,
  clampProgress,
  progressHeight,
} from './ProgressBar';
import type { ProgressSize } from './ProgressBar';

interface FieldProgressProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  /** Высота полосы. По умолчанию 'xl'; для крупного бара — число, напр. 24. */
  size?: ProgressSize;
  /** Шаг перетаскивания. По умолчанию 5 %. */
  step?: number;
  /**
   * Можно ли менять значение мышью. По умолчанию true (ползунок).
   * false — только показ.
   */
  editable?: boolean;
  /**
   * Имя boolean-поля формы: ползунок активен, только пока оно включено
   * (напр. «прогресс по умолчанию» стадии при галочке progress_auto).
   */
  enabledBy?: string;
  [key: string]: any;
}

interface ProgressViewProps {
  value: unknown;
  size?: ProgressSize;
  /** aria-label полосы. */
  label?: string;
}

/**
 * Полоса «только показ» + процент. Общая для формы (editable={false}) и
 * карточек канбана (fara_leads / fara_sales, extensions/KanbanCard*), поэтому
 * вид прогресса в карточке записи и в канбане одинаковый.
 */
export const ProgressView = ({ value, size = 'xl', label }: ProgressViewProps) => (
  <ProgressLine
    value={clampProgress(value) ?? 0}
    height={progressHeight(size)}
    label={label}
  />
);

/**
 * Поле-процент (0–100) полосой прогресса.
 *
 * Подключение: <Field name="progress" widget="progress" />
 *   editable={false} — только показ (вычисляемые поля);
 *   size={24}        — высота полосы;
 *   step={1}         — шаг ползунка.
 */
export const FieldProgress = ({
  name,
  label,
  labelPosition,
  required,
  size = 'xl',
  step = 5,
  editable = true,
  enabledBy,
}: FieldProgressProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;
  // disabled приходит из enhanceGetInputProps формы (поля заблокированы,
  // пока не пришли метаданные) — в типах Mantine этого свойства нет.
  const { disabled } = form.getInputProps(name) as { disabled?: boolean };
  const value = clampProgress(form.getValues()?.[name]) ?? 0;

  // enabledBy: следим за галочкой. form.watch вызывается во время рендера
  // (правило Mantine v7, как в FieldPatternBuilder); без enabledBy
  // подписка на само поле — холостая, но хук должен вызываться всегда.
  const [enabled, setEnabled] = useState(() =>
    enabledBy ? !!form.getValues()?.[enabledBy] : true,
  );
  form.watch(enabledBy ?? name, ({ value: next }: { value: unknown }) => {
    if (enabledBy) {
      setEnabled(!!next);
    }
  });

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}
      align="center">
      {editable ? (
        <ProgressSlider
          key={form.key(name)}
          value={value}
          height={progressHeight(size)}
          step={step}
          disabled={disabled || !enabled}
          label={displayLabel}
          onCommit={next => form.setFieldValue(name, next)}
        />
      ) : (
        <ProgressView
          key={form.key(name)}
          value={value}
          size={size}
          label={displayLabel}
        />
      )}
    </FieldWrapper>
  );
};
