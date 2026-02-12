import { useState, useRef } from 'react';
import type { ChangeEvent } from 'react';
import { uploadFit } from '../../api/activities.ts';
import './UploadButton.css';

interface Props {
  onUploadComplete: () => void;
}

export default function UploadButton({ onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const ext = file.name.toLowerCase().split('.').pop();
    if (ext !== 'fit' && ext !== 'zip') {
      setError('Only .fit and .zip files are supported');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');
    setProgress(0);

    try {
      await uploadFit(file, setProgress);
      setSuccess(`Uploaded ${file.name} - processing...`);
      // Wait a moment then refresh the list
      setTimeout(() => {
        onUploadComplete();
        setSuccess('');
      }, 2000);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Upload failed';
      setError(message);
    } finally {
      setUploading(false);
      setProgress(0);
      // Reset file input so same file can be re-uploaded
      if (fileRef.current) {
        fileRef.current.value = '';
      }
    }
  }

  return (
    <div className="upload-wrapper">
      <label className={`btn btn-primary ${uploading ? 'btn-uploading' : ''}`}>
        {uploading ? (
          <>
            <span className="spinner" />
            Uploading {progress}%
          </>
        ) : (
          'Upload FIT'
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".fit,.zip"
          onChange={handleFileChange}
          disabled={uploading}
          className="sr-only"
        />
      </label>
      {error && <span className="upload-error">{error}</span>}
      {success && <span className="upload-success">{success}</span>}
    </div>
  );
}
