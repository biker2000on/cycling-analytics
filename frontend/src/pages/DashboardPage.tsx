import { useEffect } from 'react';
import { useMetricsStore } from '../stores/metricsStore.ts';
import FitnessChart from '../components/charts/FitnessChart.tsx';
import DateRangePicker from '../components/charts/DateRangePicker.tsx';
import ThresholdMethodSelector from '../components/charts/ThresholdMethodSelector.tsx';
import FitnessSnapshot from '../components/dashboard/FitnessSnapshot.tsx';
import RecentActivities from '../components/dashboard/RecentActivities.tsx';
import TrainingSummary from '../components/dashboard/TrainingSummary.tsx';
import './DashboardPage.css';

export default function DashboardPage() {
  const {
    fitnessData,
    fitnessLoading,
    fitnessError,
    dateRangePreset,
    startDate,
    endDate,
    thresholdMethod,
    setDateRangePreset,
    setCustomDateRange,
    setThresholdMethod,
    fetchFitnessData,
  } = useMetricsStore();

  useEffect(() => {
    fetchFitnessData();
  }, [fetchFitnessData]);

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
      </div>

      {/* Fitness Snapshot */}
      <FitnessSnapshot data={fitnessData} loading={fitnessLoading} />

      {/* PMC Controls */}
      <div className="dashboard-controls card">
        <div className="dashboard-controls-row">
          <DateRangePicker
            preset={dateRangePreset}
            startDate={startDate}
            endDate={endDate}
            onPresetChange={setDateRangePreset}
            onCustomChange={setCustomDateRange}
          />
          <ThresholdMethodSelector value={thresholdMethod} onChange={setThresholdMethod} />
        </div>
      </div>

      {/* Fitness Chart (PMC) */}
      <div className="card dashboard-chart-card">
        <h2 className="dashboard-section-title">Performance Management Chart</h2>
        {fitnessError && (
          <div className="alert alert-error">{fitnessError}</div>
        )}
        {fitnessLoading ? (
          <div className="loading-state">
            <span className="spinner" /> Loading fitness data...
          </div>
        ) : fitnessData ? (
          <FitnessChart data={fitnessData.data} />
        ) : (
          <div className="chart-empty">No fitness data available.</div>
        )}
      </div>

      {/* Bottom widgets */}
      <div className="dashboard-bottom-grid">
        <RecentActivities />
        <TrainingSummary />
      </div>
    </div>
  );
}
