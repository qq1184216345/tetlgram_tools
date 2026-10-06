import { useState } from "react";
import { API_BASE } from "../config/ports";
import { useToast } from "../context/ToastContext";

interface MediaUploadProps {
  onUploaded: (path: string, filename: string) => void;
  accept?: string;
  label?: string;
}

export function MediaUpload({ onUploaded, accept, label = "选择文件" }: MediaUploadProps) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);
  const [filename, setFilename] = useState("");

  async function handleUpload(file: File) {
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/api/uploads/media`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "上传失败" }));
        throw new Error(err.detail);
      }
      const result = await response.json();
      setFilename(result.data.filename);
      onUploaded(result.data.path, result.data.filename);
      toast.success(`已上传: ${result.data.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="media-upload">
      <label className="upload-btn">
        {uploading ? "上传中..." : label}
        <input
          type="file"
          accept={accept}
          hidden
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
          }}
        />
      </label>
      {filename && <span className="muted">已选: {filename}</span>}
    </div>
  );
}
