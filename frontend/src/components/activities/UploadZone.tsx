import { useState, useRef, useCallback } from 'react';
import type { DragEvent } from 'react';
import { uploadMultiple } from '../../api/activities.ts';
import type { FileUploadResult } from '../../api/types.ts';
import ProcessingStatus from './ProcessingStatus.tsx';
import './UploadZone.css';

interface FileUploadState {
  file: File;
  status: 'waiting' | 'uploading' | 'processing' | 'done' | 'error';
  progress: number;
  taskId?: string;
  activityId?: number;
  error?: string;
}

interface Props {
  onUploadComplete: () => void;
}

const ALLOWED_EXTENSIONS = new Set(['fit', 'zip']);

function getExtension(name: string): string {
  return name.toLowerCase().split('.').pop() ?? '';
}

function validateFiles(fileList: FileList | File[]): {
  valid: File[];
  rejected: string[];
} {
  const valid: File[] = [];
  const rejected: string[] = [];
  const arr = Array.from(fileList);

  for (const f of arr) {
    if (ALLOWED_EXTENSIONS.has(getExtension(f.name))) {
      valid.push(f);
    } else {
      rejected.push(f.name);
    }
  }

  return { valid, rejected };
}

export default function UploadZone({ onUploadComplete }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<FileUploadState[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  const handleFiles = useCallback(
    async (incoming: File[]) => {
      const { valid, rejected } = validateFiles(incoming);

      if (rejected.length > 0) {
        setError(
          `Unsupported file${rejected.length > 1 ? 's' : ''}: ${rejected.join(', ')}. Only .fit and .zip files are accepted.`,
        );
      } else {
        setError('');
      }

      if (valid.length === 0) return;

      const fileStates: FileUploadState[] = valid.map((f) => ({
        file: f,
        status: 'uploading',
        progress: 0,
      }));

      setFiles(fileStates);
      setUploading(true);
      setSummary('');

      try {
        const response = await uploadMultiple(valid, (percent) => {
          setFiles((prev) =>
            prev.map((fs) => ({
              ...fs,
              status: fs.status === 'error' || fs.status === 'done' ? fs.status : 'uploading',
              progress: percent,
            })),
          );
        });

        // Map results back to file states
        setFiles((prev) =>
          prev.map((fs) => {
            const result: FileUploadResult | undefined = response.uploads.find(
              (u) => u.filename === fs.file.name,
            );
            if (!result) return { ...fs, status: 'done', progress: 100 };

            if (result.error) {
              return {
                ...fs,
                status: 'error',
                progress: 100,
                error: result.error,
              };
            }

            return {
              ...fs,
              status: result.task_id ? 'processing' : 'done',
              progress: 100,
              taskId: result.task_id ?? undefined,
              activityId: result.activity_id ?? undefined,
            };
          }),
        );

        setSummary(
          `${response.successful} of ${response.total_files} file${response.total_files !== 1 ? 's' : ''} uploaded successfully.`,
        );

        // Refresh activity list after a short delay to allow processing to start
        setTimeout(() => {
          onUploadComplete();
        }, 1500);
      } catch (err: unknown) {
        const message =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail || 'Upload failed';

        setFiles((prev) =>
          prev.map((fs) => ({
            ...fs,
            status: 'error',
            error: message,
          })),
        );
        setError(message);
      } finally {
        setUploading(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    },
    [onUploadComplete],
  );

  /* ── Drag handlers ────────────────────────────────────────────────── */

  function handleDragEnter(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current += 1;
    if (dragCounterRef.current === 1) {
      setIsDragging(true);
    }
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);

    if (uploading) return;

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      handleFiles(droppedFiles);
    }
  }

  /* ── Click-to-browse ──────────────────────────────────────────────── */

  function handleBrowseClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (!uploading) {
      fileInputRef.current?.click();
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files;
    if (selected && selected.length > 0) {
      handleFiles(Array.from(selected));
    }
  }

  function handleZoneClick() {
    if (!uploading) {
      fileInputRef.current?.click();
    }
  }

  /* ── Status labels ────────────────────────────────────────────────── */

  function statusLabel(status: FileUploadState['status']): string {
    switch (status) {
      case 'waiting':
        return 'Waiting';
      case 'uploading':
        return 'Uploading';
      case 'processing':
        return 'Processing';
      case 'done':
        return 'Done';
      case 'error':
        return 'Error';
    }
  }

  /* ── Render ───────────────────────────────────────────────────────── */

  const zoneClasses = [
    'upload-zone',
    isDragging ? 'upload-zone--dragging' : '',
    uploading ? 'upload-zone--uploading' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={zoneClasses}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleZoneClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') handleZoneClick();
      }}
    >
      <div className="upload-zone__prompt">
        <span className="upload-zone__icon" aria-hidden="true">
          {isDragging ? '\u2B07' : '\u2B06'}
        </span>
        <span className="upload-zone__text">
          {isDragging
            ? 'Drop files here'
            : 'Drop .fit or .zip files here'}
        </span>
        {!isDragging && (
          <button
            type="button"
            className="upload-zone__browse"
            onClick={handleBrowseClick}
            disabled={uploading}
          >
            or browse
          </button>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".fit,.zip"
        multiple
        onChange={handleInputChange}
        disabled={uploading}
        className="sr-only"
      />

      {/* File list */}
      {files.length > 0 && (
        <div className="upload-zone__file-list" onClick={(e) => e.stopPropagation()}>
          {files.map((fs, idx) => (
            <div className="upload-zone__file-item" key={`${fs.file.name}-${idx}`}>
              {/* Show ProcessingStatus for files being processed by backend */}
              {fs.status === 'processing' && fs.taskId ? (
                <ProcessingStatus
                  taskId={fs.taskId}
                  filename={fs.file.name}
                  onComplete={() => {
                    setFiles((prev) =>
                      prev.map((f, i) =>
                        i === idx ? { ...f, status: 'done' } : f,
                      ),
                    );
                    onUploadComplete();
                  }}
                />
              ) : (
                <>
                  <span className="upload-zone__file-name">{fs.file.name}</span>

                  {(fs.status === 'uploading' || fs.status === 'waiting') && (
                    <div className="upload-zone__progress-wrapper">
                      <div
                        className="upload-zone__progress-bar"
                        style={{ width: `${fs.progress}%` }}
                      />
                    </div>
                  )}

                  {fs.status === 'done' && (
                    <div className="upload-zone__progress-wrapper">
                      <div
                        className="upload-zone__progress-bar upload-zone__progress-bar--done"
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}

                  {fs.status === 'error' && (
                    <div className="upload-zone__progress-wrapper">
                      <div
                        className="upload-zone__progress-bar upload-zone__progress-bar--error"
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}

                  <span
                    className={`upload-zone__file-status upload-zone__file-status--${fs.status}`}
                  >
                    {statusLabel(fs.status)}
                  </span>
                </>
              )}
            </div>
          ))}

          {files.some((fs) => fs.status === 'error' && fs.error) &&
            files
              .filter((fs) => fs.status === 'error' && fs.error)
              .map((fs, idx) => (
                <div className="upload-zone__error" key={`err-${idx}`}>
                  {fs.file.name}: {fs.error}
                </div>
              ))}
        </div>
      )}

      {error && files.length === 0 && (
        <div className="upload-zone__error">{error}</div>
      )}

      {summary && <div className="upload-zone__summary">{summary}</div>}
    </div>
  );
}
