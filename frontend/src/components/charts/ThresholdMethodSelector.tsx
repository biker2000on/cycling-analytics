import type { ThresholdMethod } from '../../stores/metricsStore.ts';

interface Props {
  value: ThresholdMethod;
  onChange: (method: ThresholdMethod) => void;
}

const METHODS: { value: ThresholdMethod; label: string }[] = [
  { value: 'manual', label: 'Manual FTP' },
  { value: '95_20min', label: '95% of 20 min' },
  { value: '90_8min', label: '90% of 8 min' },
];

export default function ThresholdMethodSelector({ value, onChange }: Props) {
  return (
    <select
      className="threshold-select"
      value={value}
      onChange={(e) => onChange(e.target.value as ThresholdMethod)}
    >
      {METHODS.map((m) => (
        <option key={m.value} value={m.value}>
          {m.label}
        </option>
      ))}
    </select>
  );
}
