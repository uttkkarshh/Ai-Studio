import { useRef, useState } from 'react';

const targetLabels = {
  part: 'Part',
  finding: 'Finding',
  source: 'Source',
  script_draft: 'Script Draft',
};

function hasOnlyKeys(draft, keys) {
  return Object.keys(draft).every((key) => keys.includes(key));
}

function validateDraft(targetType, draft) {
  const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const validIds = (value) => Array.isArray(value) && value.every((id) => Number.isInteger(id) && id > 0);
  const validStructuredContent = (value) => value == null || Array.isArray(value) || isRecord(value);

  if (!isRecord(draft)) return 'Draft content must be a JSON object.';
  if (targetType === 'part') {
    if (!hasOnlyKeys(draft, ['title', 'objective', 'description', 'status', 'position'])) return 'Part draft contains unsupported fields.';
    if (typeof draft.title !== 'string' || !draft.title.trim()) return 'Part title is required.';
    if (draft.objective != null && typeof draft.objective !== 'string') return 'Part objective must be text or null.';
    if (draft.description != null && typeof draft.description !== 'string') return 'Part description must be text or null.';
    if (typeof draft.status !== 'string') return 'Part status must be text.';
    if (!Number.isInteger(draft.position)) return 'Part position must be a whole number.';
  } else if (targetType === 'finding') {
    if (!hasOnlyKeys(draft, ['heading', 'content', 'created_by_type', 'status', 'part_ids', 'source_ids'])) return 'Finding draft contains unsupported fields.';
    if (typeof draft.heading !== 'string' || !draft.heading.trim()) return 'Finding heading is required.';
    if (!validStructuredContent(draft.content)) return 'Finding content must be a JSON object, array, or null.';
    if (!['user', 'ai', 'imported'].includes(draft.created_by_type)) return 'Finding created_by_type must be user, ai, or imported.';
    if (!['draft', 'active', 'archived'].includes(draft.status)) return 'Finding status must be draft, active, or archived.';
    if (!validIds(draft.part_ids)) return 'Finding part_ids must contain positive whole numbers.';
    if (!validIds(draft.source_ids)) return 'Finding source_ids must contain positive whole numbers.';
  } else if (targetType === 'source') {
    if (!hasOnlyKeys(draft, ['title', 'url', 'source_type', 'content', 'metadata', 'part_ids'])) return 'Source draft contains unsupported fields.';
    if (typeof draft.title !== 'string' || !draft.title.trim()) return 'Source title is required.';
    if (draft.url != null && typeof draft.url !== 'string') return 'Source URL must be text or null.';
    if (typeof draft.source_type !== 'string' || !draft.source_type.trim()) return 'Source type is required.';
    if (draft.content != null && typeof draft.content !== 'string') return 'Source content must be text or null.';
    if (draft.metadata != null && !isRecord(draft.metadata)) return 'Source metadata must be a JSON object or null.';
    if (!validIds(draft.part_ids)) return 'Source part_ids must contain positive whole numbers.';
  } else if (targetType === 'script_draft') {
    if (!hasOnlyKeys(draft, ['title', 'content', 'created_by_type'])) return 'Script Draft contains unsupported fields.';
    if (draft.title != null && typeof draft.title !== 'string') return 'Script title must be text or null.';
    if (!validStructuredContent(draft.content)) return 'Script content must be a JSON object, array, or null.';
    if (typeof draft.created_by_type !== 'string') return 'Script created_by_type must be text.';
  } else {
    return `Draft target "${targetType}" is not supported for review.`;
  }
  return '';
}

function DraftValue({ value }) {
  if (value == null) return <span className="draft-value-empty">Not provided</span>;
  if (typeof value !== 'object') return <span>{String(value)}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="draft-value-empty">None</span>;
    return (
      <ul className="draft-value-list">
        {value.map((item, index) => <li key={index}><DraftValue value={item} /></li>)}
      </ul>
    );
  }
  const entries = Object.entries(value);
  if (entries.length === 0) return <span className="draft-value-empty">No details</span>;
  return (
    <dl className="draft-value-object">
      {entries.map(([key, entry]) => (
        <div key={key}>
          <dt>{key.replaceAll('_', ' ')}</dt>
          <dd><DraftValue value={entry} /></dd>
        </div>
      ))}
    </dl>
  );
}

function DraftContent({ draft }) {
  return (
    <dl className="draft-content">
      {Object.entries(draft || {}).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll('_', ' ')}</dt>
          <dd><DraftValue value={value} /></dd>
        </div>
      ))}
    </dl>
  );
}

export default function DraftResults({
  results,
  plan,
  status,
  error,
  parts,
  persistence = {},
  onAccept,
  onReject,
  onUpdateDraft,
}) {
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [draftText, setDraftText] = useState('');
  const [editError, setEditError] = useState('');
  const [acceptError, setAcceptError] = useState('');
  const [rejectError, setRejectError] = useState('');
  const rejectInProgress = useRef(new Set());
  const acceptInProgress = useRef(new Set());
  const taskById = new Map((plan?.tasks || []).map((task) => [task.task_id, task]));

  function beginEditing(result) {
    setEditingTaskId(result.task_id);
    setDraftText(JSON.stringify(result.draft, null, 2));
    setEditError('');
  }

  function saveDraft(result) {
    let updatedDraft;
    try {
      updatedDraft = JSON.parse(draftText);
    } catch {
      setEditError('Draft must contain valid JSON.');
      return;
    }
    const validationError = validateDraft(result.target_type, updatedDraft);
    if (validationError) {
      setEditError(validationError);
      return;
    }
    onUpdateDraft(result.task_id, updatedDraft);
    setEditingTaskId(null);
    setEditError('');
  }

  async function rejectDraft(taskId) {
    if (rejectInProgress.current.has(taskId)) return;
    if (!window.confirm('Reject this generated draft? It will be removed from this review only; project data will not be changed.')) return;
    rejectInProgress.current.add(taskId);
    setRejectError('');
    try {
      onReject(taskId);
    } catch (rejectActionError) {
      setRejectError(rejectActionError.message || 'Unable to reject this draft.');
    } finally {
      rejectInProgress.current.delete(taskId);
    }
  }

  async function acceptDraft(result, savedState) {
    if (acceptInProgress.current.has(result.task_id)) return;
    acceptInProgress.current.add(result.task_id);
    setAcceptError('');
    try {
      await onAccept(result, result.draft, savedState);
    } catch (acceptFailure) {
      setAcceptError(acceptFailure.message || 'Unable to accept this draft.');
    } finally {
      acceptInProgress.current.delete(result.task_id);
    }
  }

  return (
    <section className="card-panel draft-results-panel" aria-labelledby="draft-results-title">
      <h3 id="draft-results-title">Draft Results</h3>
      {error ? <p className="feedback-error" role="alert">{error}</p> : null}
      {status ? <p className="draft-results-status" role="status">{status}</p> : null}
      <p className="meta-label">Each generated draft is saved only after you accept it; generation alone does not persist project data.</p>
      {rejectError ? <p className="feedback-error" role="alert">{rejectError}</p> : null}
      {acceptError ? <p className="feedback-error" role="alert">{acceptError}</p> : null}
      <div className="draft-result-list">
        {results.map((result) => {
          const task = taskById.get(result.task_id);
          const savedState = persistence[result.task_id] || {};
          const isDraftReady = result.status === 'draft_ready' && result.draft != null;
          const isEditing = editingTaskId === result.task_id;
          return (
            <article className="draft-result-card" key={result.task_id}>
              <div className="proposal-task-heading">
                <h4>{task?.title || result.task_id}</h4>
                <span className="tag">{result.task_id}</span>
              </div>
              <p><strong>Target type:</strong> {targetLabels[result.target_type] || result.target_type}</p>
              <p><strong>Execution status:</strong> {result.status.replaceAll('_', ' ')}</p>
              {result.error ? <p className="feedback-error" role="alert">{result.error}</p> : null}
              {result.clarification_questions?.length ? (
                <div>
                  <strong>Clarification required</strong>
                  <ul>{result.clarification_questions.map((question, index) => <li key={index}>{question}</li>)}</ul>
                </div>
              ) : null}
              {result.validation?.warnings?.length ? (
                <ul className="draft-warning-list">
                  {result.validation.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
                </ul>
              ) : null}
              {isDraftReady ? (
                <>
                  {isEditing ? (
                    <div className="editor-form draft-editor">
                      <label>
                        Draft JSON
                        <textarea
                          aria-label={`Edit ${task?.title || result.task_id} draft JSON`}
                          rows={12}
                          value={draftText}
                          onChange={(event) => setDraftText(event.target.value)}
                        />
                      </label>
                      {editError ? <p className="feedback-error" role="alert">{editError}</p> : null}
                      <div className="action-row">
                        <button type="button" className="primary-button" onClick={() => saveDraft(result)}>Save draft edits</button>
                        <button type="button" className="secondary-button" onClick={() => { setEditingTaskId(null); setEditError(''); }}>Cancel edit</button>
                      </div>
                    </div>
                  ) : <DraftContent draft={result.draft} />}
                  {result.target_type === 'script_draft' && !savedState.draftId ? (
                    <label className="draft-part-picker">
                      Save script draft to Part
                      <select
                        value={savedState.partId || ''}
                        onChange={(event) => onUpdateDraft(result.task_id, result.draft, { partId: event.target.value ? Number(event.target.value) : null })}
                      >
                        <option value="">Choose a Part</option>
                        {parts.map((part) => <option key={part.id} value={part.id}>{part.title} (#{part.id})</option>)}
                      </select>
                    </label>
                  ) : null}
                  {savedState.status === 'persisted' ? (
                    <p className="feedback-message" role="status">Saved and accepted by the backend.</p>
                  ) : savedState.status === 'saved_draft' ? (
                    <p className="feedback-warning" role="status">
                      Script draft #{savedState.draftId} is saved, but was not accepted as a script revision. {savedState.error || ''}
                    </p>
                  ) : null}
                  {savedState.error && savedState.status !== 'saved_draft' ? <p className="feedback-error" role="alert">{savedState.error}</p> : null}
                  <div className="action-row">
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={Boolean(savedState.status === 'persisted' || savedState.status === 'saving' || savedState.status === 'saved_draft')}
                      onClick={() => beginEditing(result)}
                    >
                      Edit Draft
                    </button>
                    {savedState.status !== 'persisted' ? (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={Boolean(savedState.status === 'saving' || isEditing || (result.target_type === 'script_draft' && !savedState.partId && !savedState.draftId))}
                        onClick={() => acceptDraft(result, savedState)}
                      >
                        {savedState.status === 'saving' ? 'Saving...' : savedState.status === 'saved_draft' ? 'Accept Script Draft' : 'Accept Draft'}
                      </button>
                    ) : null}
                    {savedState.status !== 'persisted' && savedState.status !== 'saved_draft' ? (
                      <button type="button" className="danger-button" onClick={() => rejectDraft(result.task_id)}>Reject Draft</button>
                    ) : null}
                  </div>
                </>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
