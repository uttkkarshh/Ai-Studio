export default function EmptyState({ title, message, action }) {
  return (
    <div className="state-panel empty-panel">
      <p className="state-title">{title}</p>
      {message ? <p>{message}</p> : null}
      {action ? <div className="state-action">{action}</div> : null}
    </div>
  );
}
