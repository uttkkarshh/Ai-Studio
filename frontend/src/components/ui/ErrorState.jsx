export default function ErrorState({ message, onRetry }) {
  return (
    <div className="state-panel error-panel">
      <p className="state-title">Something went wrong</p>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="primary-button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
