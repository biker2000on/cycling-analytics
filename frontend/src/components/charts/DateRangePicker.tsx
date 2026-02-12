import type { DateRangePreset } from '../../stores/metricsStore.ts';
import './DateRangePicker.css';

interface Props {
  preset: DateRangePreset;
  startDate: string;
  endDate: string;
  onPresetChange: (preset: DateRangePreset) => void;
  onCustomChange: (startDate: string, endDate: string) => void;
}

const PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: '6m', label: '6 months' },
  { value: '1y', label: '1 year' },
  { value: 'all', label: 'All' },
];

export default function DateRangePicker({
  preset,
  startDate,
  endDate,
  onPresetChange,
  onCustomChange,
}: Props) {
  return (
    <div className="date-range-picker">
      <div className="date-range-presets">
        {PRESETS.map((p) => (
          <button
            key={p.value}
            className={`date-range-btn${preset === p.value ? ' date-range-btn-active' : ''}`}
            onClick={() => onPresetChange(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="date-range-custom">
        <input
          type="date"
          className="date-input"
          value={startDate}
          onChange={(e) => onCustomChange(e.target.value, endDate)}
        />
        <span className="date-range-separator">to</span>
        <input
          type="date"
          className="date-input"
          value={endDate}
          onChange={(e) => onCustomChange(startDate, e.target.value)}
        />
      </div>
    </div>
  );
}
