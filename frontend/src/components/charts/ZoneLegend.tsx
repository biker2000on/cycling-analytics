import type { ZoneBoundary } from '../../utils/powerZones.ts';
import { getZoneBoundaries } from '../../utils/powerZones.ts';
import './ZoneLegend.css';

interface Props {
  ftp: number;
}

export default function ZoneLegend({ ftp }: Props) {
  const zones: ZoneBoundary[] = getZoneBoundaries(ftp);

  return (
    <div className="zone-legend">
      {zones.map((z) => (
        <div key={z.zone} className="zone-legend-item">
          <span className="zone-legend-swatch" style={{ backgroundColor: z.color }} />
          <span className="zone-legend-label">
            Z{z.zone} {z.name}
          </span>
          <span className="zone-legend-range">
            {z.zone < 7 ? `${z.min}-${z.max}W` : `>${z.min}W`}
          </span>
        </div>
      ))}
    </div>
  );
}
