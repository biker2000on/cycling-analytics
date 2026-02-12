import { useEffect } from 'react';
import { useActivityStore } from '../stores/activityStore.ts';
import ActivityTable from '../components/activities/ActivityTable.tsx';
import UploadZone from '../components/activities/UploadZone.tsx';
import Pagination from '../components/common/Pagination.tsx';
import './ActivityListPage.css';

export default function ActivityListPage() {
  const {
    activities,
    total,
    loading,
    error,
    page,
    pageSize,
    sortField,
    sortDir,
    fetchActivities,
    setPage,
    setSort,
  } = useActivityStore();

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities, page, sortField, sortDir]);

  function handlePageChange(newPage: number) {
    setPage(newPage);
  }

  return (
    <div className="activity-list-page">
      <div className="page-header">
        <h1 className="page-title">Activities</h1>
      </div>

      <UploadZone onUploadComplete={fetchActivities} />

      {error && <div className="alert alert-error">{error}</div>}

      {loading && activities.length === 0 ? (
        <div className="loading-state">
          <span className="spinner" /> Loading activities...
        </div>
      ) : activities.length === 0 ? (
        <div className="empty-state card">
          <h2>No activities yet</h2>
          <p>Upload a FIT file to get started.</p>
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 0 }}>
            <ActivityTable
              activities={activities}
              sortField={sortField}
              sortDir={sortDir}
              onSort={setSort}
            />
          </div>
          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={handlePageChange}
          />
        </>
      )}
    </div>
  );
}
