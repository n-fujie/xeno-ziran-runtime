import { NATIVE, nativeShare } from '../../api/native';

/** Save a text file: the share sheet on iOS, a download elsewhere (the in-tab runtime also downloads). */
export function saveText(filename: string, mime: string, text: string): void {
  if (NATIVE) { void nativeShare(filename, mime, text); return; }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}
