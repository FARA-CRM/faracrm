/**
 * Полоса прогресса и ползунок для процентных полей.
 *
 * Один вид на два места:
 *   • поле «Прогресс» в карточке записи — `FieldProgress` (`widget="progress"`);
 *   • карточка канбана лидов и заказов — `ProgressView` в
 *     `fara_leads/extensions/KanbanCardLead` и `fara_sales/extensions/KanbanCardSale`.
 *
 * Пять ступеней вместо трёх (25 / 50 / 75 / 100 %), градиент, блик, медленный
 * отблеск, процент с цветной точкой и галочкой на 100 %. Ползунок — нативный
 * `input[type=range]`: клавиатура, тач и скринридеры работают штатно, а заливка
 * считается по той же формуле, по которой браузер ставит бегунок.
 *
 * Цвета — обычные hex/rgb, без привязки к теме: полоса читается и на светлой,
 * и на тёмной карточке.
 */
import { useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { IconCheck } from '@tabler/icons-react';

import classes from './FieldProgress.module.css';

export interface ProgressTone {
  /** Начало градиента (он же — цвет точки и галочки). */
  from: string;
  /** Конец градиента. */
  to: string;
  /** Свечение под полосой (rgba с прозрачностью). */
  glow: string;
}

interface ToneStop extends ProgressTone {
  /** Верхняя граница диапазона включительно. */
  upTo: number;
}

const TONES: ToneStop[] = [
  // 0–25 %: только начали — тёплый оранжевый.
  { upTo: 25, from: '#e8590c', to: '#ff922b', glow: 'rgb(232 89 12 / 35%)' },
  // 26–50 %: в работе — янтарный.
  { upTo: 50, from: '#f08c00', to: '#ffd43b', glow: 'rgb(240 140 0 / 35%)' },
  // 51–75 %: больше половины — синий.
  { upTo: 75, from: '#1c7ed6', to: '#4dabf7', glow: 'rgb(28 126 214 / 35%)' },
  // 76–99 %: почти готово — бирюзовый.
  { upTo: 99, from: '#0c8599', to: '#22b8cf', glow: 'rgb(12 133 153 / 35%)' },
  // 100 %: закрыто — зелёный.
  { upTo: 100, from: '#099268', to: '#38d9a9', glow: 'rgb(9 146 104 / 40%)' },
];

/** Тон полосы для значения 0–100. */
export function progressTone(value: number): ProgressTone {
  const stop = TONES.find(item => value <= item.upTo) ?? TONES[TONES.length - 1];
  return { from: stop.from, to: stop.to, glow: stop.glow };
}

/** 0–100; null — значения нет (блок не рисуем). */
export function clampProgress(raw: unknown): number | null {
  if (raw === null || raw === undefined || raw === '') return null;
  const num = Number(raw);
  if (!Number.isFinite(num)) return null;
  return Math.max(0, Math.min(100, Math.round(num)));
}

/** Высота полосы: mantine-размер ('xs'…'xl') или пиксели. */
export type ProgressSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number;

const HEIGHT_BY_SIZE: Record<string, number> = {
  xs: 3,
  sm: 5,
  md: 8,
  lg: 12,
  xl: 16,
};

/** Пиксельная высота полосы для размера (как у Progress из Mantine). */
export const progressHeight = (size: ProgressSize = 'xl'): number =>
  typeof size === 'number' ? size : (HEIGHT_BY_SIZE[size] ?? 16);

interface ProgressBarProps {
  value: number;
  /** Толщина полосы, px. */
  height?: number;
  /** Подпись для скринридера (локализованное «Прогресс»). */
  label?: string;
}

/** Полоса: дорожка + градиентная заливка, блик и бегущий отблеск. */
export function ProgressBar({ value, height = 6, label }: ProgressBarProps) {
  const tone = progressTone(value);

  return (
    <div
      className={classes.track}
      style={{ height }}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      aria-valuetext={`${value}%`}
      aria-label={label}>
      <div
        className={classes.fill}
        style={{
          width: `${value}%`,
          backgroundImage: `linear-gradient(90deg, ${tone.from}, ${tone.to})`,
          boxShadow: `0 0 10px ${tone.glow}`,
        }}
      />
    </div>
  );
}

/** Процент с цветной точкой; на 100 % — галочка. */
export function ProgressValue({ value }: { value: number }) {
  const tone = progressTone(value);
  const done = value >= 100;

  return (
    <span className={classes.value}>
      {done ? (
        <IconCheck
          className={classes.check}
          size={12}
          stroke={3}
          color={tone.from}
        />
      ) : (
        <span className={classes.dot} style={{ backgroundColor: tone.from }} />
      )}
      {value}%
    </span>
  );
}

/** Строка «полоса + процент»: канбан и режим просмотра в форме. */
export function ProgressLine({ value, height = 6, label }: ProgressBarProps) {
  return (
    <div className={classes.line}>
      <ProgressBar value={value} height={height} label={label} />
      <ProgressValue value={value} />
    </div>
  );
}

interface ProgressSliderProps {
  value: number;
  height: number;
  step: number;
  disabled?: boolean;
  /** Подпись для скринридера (локализованное название поля). */
  label?: string;
  /** Значение уходит в форму по окончании перетаскивания (как onChangeEnd). */
  onCommit: (value: number) => void;
}

/**
 * Редактируемый ползунок. Отдельное состояние нужно потому, что форма
 * uncontrolled и о промежуточных значениях не знает, а монтируется он по
 * `form.key(name)` — значение извне (загрузка записи, `/onchange`) сбрасывает
 * локальное.
 */
export function ProgressSlider({
  value,
  height,
  step,
  disabled,
  label,
  onCommit,
}: ProgressSliderProps) {
  const [current, setCurrent] = useState(value);
  // Последнее значение — в ref: pointerup/keyup может прийти раньше, чем
  // React применит setState из onChange, и тогда в форму уйдёт старое число.
  const latest = useRef(value);

  const handleChange = (next: number) => {
    latest.current = next;
    setCurrent(next);
  };
  const commit = () => onCommit(latest.current);

  const tone = progressTone(current);
  const thumb = Math.min(28, Math.max(16, Math.round(height * 1.6)));

  return (
    <div className={classes.line}>
      <input
        type="range"
        className={classes.range}
        min={0}
        max={100}
        step={step}
        value={current}
        disabled={disabled}
        aria-label={label}
        onChange={event => handleChange(Number(event.currentTarget.value))}
        onPointerUp={commit}
        onKeyUp={commit}
        onBlur={commit}
        style={
          {
            '--track-height': `${height}px`,
            '--thumb-size': `${thumb}px`,
            '--p': `${current / 100}`,
            '--tone-from': tone.from,
            '--tone-to': tone.to,
          } as CSSProperties
        }
      />
      <ProgressValue value={current} />
    </div>
  );
}

