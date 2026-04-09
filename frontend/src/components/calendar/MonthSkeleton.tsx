import './MonthView.css';

const DAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function MonthSkeleton() {
  // Render 5 skeleton weeks to match typical month height
  const weeks = [0, 1, 2, 3, 4];

  return (
    <div className="month-view">
      <div className="month-header-row">
        {DAY_HEADERS.map((h) => (
          <div key={h} className="month-header-cell">{h}</div>
        ))}
        <div className="month-header-cell month-header-summary">Week</div>
      </div>

      {weeks.map((wi) => (
        <div key={wi} className="month-week-row">
          <div className="month-day-cells">
            {[0, 1, 2, 3, 4, 5, 6].map((di) => (
              <div key={di} className="day-cell day-cell-skeleton">
                <span className="skeleton-bar skeleton-day-num" />
              </div>
            ))}
          </div>
          <div className="weekly-summary weekly-summary-empty">
            <span className="skeleton-bar skeleton-week-label" />
          </div>
        </div>
      ))}
    </div>
  );
}
