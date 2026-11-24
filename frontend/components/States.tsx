export function LoadingState({
  title = "Simulando temporadas",
  note,
}: {
  title?: string;
  note?: string;
}) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <strong>{title}</strong>
      {note ? <span>{note}</span> : null}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <strong>No se pudo cargar</strong>
      <span>{message}</span>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function SkeletonPanel({ height = 280 }: { height?: number }) {
  return (
    <div className="panel" aria-hidden="true">
      <div className="panel-head">
        <div className="skeleton skeleton-line short" />
      </div>
      <div className="panel-body">
        <div className="skeleton" style={{ height }} />
      </div>
    </div>
  );
}
