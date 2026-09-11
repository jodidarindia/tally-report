import React, { useCallback, useRef, useState } from 'react';
import ReactCrop, { centerCrop, makeAspectCrop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import axios from 'axios';
import { toast } from 'sonner';
import { X, Upload, Loader, Crop as CropIcon } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const MAX_BYTES = 5 * 1024 * 1024;
const ASPECT_PRESETS = [
  { id: 'free', label: 'Free', ratio: undefined },
  { id: '16:9', label: '16:9', ratio: 16 / 9 },
  { id: '4:3',  label: '4:3',  ratio: 4 / 3 },
  { id: '1:1',  label: '1:1',  ratio: 1 },
];

const centeredCrop = (mediaW, mediaH, aspect) => {
  if (!aspect) return { unit: '%', x: 5, y: 5, width: 90, height: 90 };
  return centerCrop(
    makeAspectCrop({ unit: '%', width: 90 }, aspect, mediaW, mediaH),
    mediaW,
    mediaH,
  );
};

/**
 * ImageCropUpload — pick a file, optionally crop with a preset aspect
 * ratio, then upload to Emergent Object Storage. On success, calls
 * `onUploaded({url, path})` with the served URL.
 *
 * Props:
 *   open        boolean
 *   onClose     () => void
 *   onUploaded  ({url, path}) => void
 *   token       auth token for the upload endpoint
 *   aspect      optional forced aspect ratio (used for cover images)
 */
export const ImageCropUpload = ({ open, onClose, onUploaded, token, aspect: forcedAspect }) => {
  const [file, setFile]           = useState(null);
  const [preview, setPreview]     = useState('');
  const [crop, setCrop]           = useState();
  const [completedCrop, setCompletedCrop] = useState();
  const [aspectId, setAspectId]   = useState(forcedAspect ? '16:9' : 'free');
  const [uploading, setUploading] = useState(false);
  const imgRef  = useRef(null);

  const aspect = forcedAspect ?? ASPECT_PRESETS.find(p => p.id === aspectId)?.ratio;

  const reset = () => {
    setFile(null); setPreview(''); setCrop(); setCompletedCrop();
    setAspectId(forcedAspect ? '16:9' : 'free');
  };
  const close = () => { reset(); onClose?.(); };

  const onFilePick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(f.type)) {
      toast.error('Only JPG, PNG, WebP, or GIF images.'); return;
    }
    if (f.size > MAX_BYTES) {
      toast.error(`Image too large — max 5 MB (yours is ${(f.size/1024/1024).toFixed(1)} MB).`); return;
    }
    setFile(f);
    const r = new FileReader();
    r.onload = () => setPreview(r.result?.toString() || '');
    r.readAsDataURL(f);
  };

  const onImageLoad = useCallback((e) => {
    const { width, height } = e.currentTarget;
    setCrop(centeredCrop(width, height, aspect));
  }, [aspect]);

  const changeAspect = (id) => {
    setAspectId(id);
    const ratio = ASPECT_PRESETS.find(p => p.id === id)?.ratio;
    if (imgRef.current) {
      const { width, height } = imgRef.current;
      setCrop(centeredCrop(width, height, ratio));
      setCompletedCrop(undefined);
    }
  };

  const getCroppedBlob = async () => {
    // Returns a JPEG blob of the cropped region — falls back to the
    // original file if the user never dragged the crop box.
    if (!imgRef.current || !completedCrop?.width || !completedCrop?.height) return file;
    const img = imgRef.current;
    const scaleX = img.naturalWidth  / img.width;
    const scaleY = img.naturalHeight / img.height;
    const canvas = document.createElement('canvas');
    canvas.width  = Math.round(completedCrop.width  * scaleX);
    canvas.height = Math.round(completedCrop.height * scaleY);
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(
      img,
      completedCrop.x * scaleX, completedCrop.y * scaleY,
      completedCrop.width * scaleX, completedCrop.height * scaleY,
      0, 0, canvas.width, canvas.height,
    );
    return await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.92));
  };

  const doUpload = async () => {
    if (!file) { toast.error('Pick an image first'); return; }
    setUploading(true);
    try {
      const blob = await getCroppedBlob();
      const ext  = (blob === file ? file.name.split('.').pop() : 'jpg').toLowerCase();
      const uploadName = `blog-${Date.now()}.${ext}`;
      const form = new FormData();
      form.append('file', blob, uploadName);
      const r = await axios.post(`${API}/super-admin/blog/upload-image`, form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      if (r.data?.success) {
        const url = process.env.REACT_APP_BACKEND_URL + r.data.data.url;
        toast.success('Image uploaded');
        onUploaded?.({ url, path: r.data.data.path });
        close();
      } else {
        toast.error(r.data?.error || 'Upload failed');
      }
    } catch (e) {
      toast.error(e.response?.data?.error || e.message || 'Upload failed');
    }
    setUploading(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-[70] flex items-center justify-center p-4"
         data-testid="image-crop-modal"
         onClick={e => e.target === e.currentTarget && !uploading && close()}>
      <div className="bg-white rounded-xl w-full max-w-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <CropIcon size={18} className="text-blue-600" />
            {forcedAspect ? 'Cover Image' : 'Insert Image'}
          </h3>
          <button onClick={close} disabled={uploading}>
            <X size={18} className="text-slate-400" />
          </button>
        </div>

        {!preview ? (
          <label
            data-testid="image-file-picker"
            className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl py-12 cursor-pointer hover:bg-slate-50">
            <Upload size={28} className="text-slate-400 mb-2" />
            <span className="text-sm font-medium text-slate-700">Click to pick an image</span>
            <span className="text-xs text-slate-400 mt-1">JPG, PNG, WebP, GIF · max 5 MB</span>
            <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={onFilePick} className="hidden" />
          </label>
        ) : (
          <>
            {!forcedAspect && (
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-semibold text-slate-600">Aspect:</span>
                {ASPECT_PRESETS.map(p => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => changeAspect(p.id)}
                    disabled={uploading}
                    data-testid={`aspect-${p.id}`}
                    className={`px-3 py-1 rounded-md text-xs font-medium border ${aspectId === p.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}>
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <div className="flex justify-center bg-slate-950 rounded-lg p-2 max-h-[60vh] overflow-auto">
              <ReactCrop
                crop={crop}
                onChange={c => setCrop(c)}
                onComplete={c => setCompletedCrop(c)}
                aspect={aspect}
                keepSelection>
                <img
                  ref={imgRef}
                  src={preview}
                  alt="crop"
                  onLoad={onImageLoad}
                  style={{ maxHeight: '55vh' }}
                  data-testid="crop-source-image"
                />
              </ReactCrop>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">
              Drag the corners to adjust. Click <b>Upload</b> when ready.
            </p>
          </>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={close} disabled={uploading}
                  className="px-4 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50">
            Cancel
          </button>
          {preview && (
            <button
              onClick={doUpload}
              disabled={uploading}
              data-testid="upload-image-btn"
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5">
              {uploading ? <><Loader size={14} className="animate-spin" /> Uploading…</> : <><Upload size={14} /> Upload</>}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ImageCropUpload;
