export function BackendBanner({ apiUrl, down }: { apiUrl: string; down: boolean }) {
  if (!down) return null;
  return (
    <div className="banner" role="alert">
      Can't reach HomeFix at {apiUrl}. Is the server running?
    </div>
  );
}
