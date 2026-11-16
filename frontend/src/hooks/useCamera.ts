import { useCallback, useEffect, useRef, useState } from 'react';

export interface CameraError { title: string; detail: string }

function describe(err: unknown): CameraError {
  const name = (err as DOMException)?.name;
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return { title: 'Camera permission was blocked', detail: 'Allow camera access in the browser address bar, then press Start camera again.' };
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return { title: 'No matching camera found', detail: 'No camera of this type is connected to this device. Choose another source.' };
  }
  if (name === 'NotReadableError' || name === 'AbortError') {
    return { title: 'Camera is busy', detail: 'Another application is using the camera. Close it and try again.' };
  }
  return { title: 'Could not start the camera', detail: (err as Error)?.message || 'Unknown error' };
}

/** Browser camera access (laptop webcam, USB webcam on this device, mobile front/rear camera). */
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<CameraError | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;

  const refreshDevices = useCallback(async () => {
    if (!supported) return;
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === 'videoinput' && d.deviceId));
    } catch { /* ignore */ }
  }, [supported]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setRunning(false);
  }, []);

  /** source: 'user' (front), 'environment' (rear) or a deviceId. */
  const start = useCallback(async (source: string) => {
    setError(null);
    if (!supported) {
      setError({ title: 'Camera not available here', detail: 'This browser cannot open a camera on this page. Cameras need HTTPS (or localhost).' });
      return false;
    }
    stop();
    const video: MediaTrackConstraints = source === 'user' || source === 'environment'
      ? { facingMode: source === 'user' ? 'user' : { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { deviceId: { exact: source }, width: { ideal: 1280 }, height: { ideal: 720 } };
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
      streamRef.current = stream;
      // A camera that is unplugged or revoked ends its track.
      stream.getVideoTracks()[0].addEventListener('ended', () => {
        streamRef.current = null;
        setRunning(false);
        setError({ title: 'Camera disconnected', detail: 'The camera stopped sending video. Reconnect it and press Start camera.' });
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setRunning(true);
      refreshDevices();
      return true;
    } catch (e) {
      setError(describe(e));
      return false;
    }
  }, [supported, stop, refreshDevices]);

  /** Grab the current frame as a JPEG blob. */
  const capture = useCallback(async (quality = 0.85): Promise<Blob | null> => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext('2d')!.drawImage(v, 0, 0);
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
  }, []);

  useEffect(() => {
    refreshDevices();
    if (!supported) return;
    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices);
    return () => {
      navigator.mediaDevices.removeEventListener?.('devicechange', refreshDevices);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [supported, refreshDevices]);

  return { videoRef, running, error, devices, supported, start, stop, capture, clearError: () => setError(null) };
}
