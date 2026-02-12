import './PeriodSelector.css';

interface Props {
  value: string;
  onChange: (period: string) => void;
}

const PERIODS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
];

export default function PeriodSelector({ value, onChange }: Props) {
  return (
    <div className="period-selector">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          className={`period-btn${value === p.value ? ' period-btn-active' : ''}`}
          onClick={() => onChange(p.value)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
