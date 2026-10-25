import { useState } from 'react';
import {
  addWorkPlanTask,
  removeWorkPlanTask,
  updateWorkPlanTask,
} from '../workPlan';

const actions = [
  'research',
  'evaluate',
  'create',
  'update',
  'delete',
  'generate_draft',
  'accept',
  'restore',
  'commit',
  'request_review',
];

const targetTypes = [
  'project',
  'part',
  'source',
  'finding',
  'asset',
  'script_draft',
  'script',
  'part_relationship',
];

function createTaskDraft(task = {}) {
  return {
    task_id: task.task_id || '',
    title: task.title || '',
    action: task.action || 'research',
    capability: task.capability || '',
    target_type: task.target_type || 'project',
    target_id: task.target_id ?? '',
    intent: task.intent || '',
    expected_output: task.expected_output || '',
    completion_criteria: (task.completion_criteria || []).join('\n'),
  };
}

function taskFromForm(form, taskId) {
  const criteria = String(form.get('completion_criteria') || '')
    .split('\n')
    .map((criterion) => criterion.trim())
    .filter(Boolean);

  if (criteria.length === 0) throw new Error('Add at least one completion criterion.');

  const targetIdValue = String(form.get('target_id') || '').trim();
  const targetId = targetIdValue ? Number(targetIdValue) : null;
  if (targetId !== null && (!Number.isInteger(targetId) || targetId < 1)) {
    throw new Error('Target ID must be a positive whole number.');
  }

  return {
    task_id: taskId || String(form.get('task_id') || '').trim(),
    title: String(form.get('title') || '').trim(),
    action: String(form.get('action') || ''),
    capability: String(form.get('capability') || '').trim(),
    target_type: String(form.get('target_type') || ''),
    target_id: targetId,
    intent: String(form.get('intent') || '').trim(),
    expected_output: String(form.get('expected_output') || '').trim(),
    completion_criteria: criteria,
  };
}

export default function WorkPlanProposal({
  plan,
  status,
  validationPending,
  busy = false,
  executionBusy = false,
  executionConfirmed = false,
  executionError = '',
  onPlanChange,
  onAccept,
  onDismiss,
  onRequestChanges,
}) {
  const [taskDraft, setTaskDraft] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [formError, setFormError] = useState('');
  const approved = executionConfirmed;
  const submitting = busy || executionBusy;
  const statusLabel = executionBusy
    ? 'Executing accepted plan'
    : approved
    ? 'Backend execution response received'
      : status === 'awaiting_approval'
        ? 'Awaiting approval'
        : status === 'revised'
          ? 'Revised locally'
          : 'Proposed';

  function saveTask(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      if (taskDraft.task_id) {
        const updatedTask = taskFromForm(form, taskDraft.task_id);
        onPlanChange(updateWorkPlanTask(plan, taskDraft.task_id, updatedTask), true);
      } else {
        const newTask = taskFromForm(form);
        if (!newTask.task_id) {
          let nextNumber = plan.tasks.length + 1;
          while (plan.tasks.some((task) => task.task_id === `task-${nextNumber}`)) nextNumber += 1;
          newTask.task_id = `task-${nextNumber}`;
        }
        onPlanChange(addWorkPlanTask(plan, newTask), true);
      }
      setTaskDraft(null);
      setFormError('');
    } catch (error) {
      setFormError(error.message);
    }
  }

  async function requestChanges(event) {
    event.preventDefault();
    const requested = await onRequestChanges(feedback.trim());
    if (requested) setFeedback('');
  }

  function dismiss() {
    setTaskDraft(null);
    onDismiss();
  }

  return (
    <section className="card-panel work-plan-panel" aria-labelledby="work-plan-title">
      <div className="section-header-row work-plan-header">
        <div>
          <h3 id="work-plan-title">Proposed WorkPlan</h3>
          <span className="work-plan-status" role="status">
            {statusLabel}
          </span>
        </div>
        <div className="action-row">
          <button
            type="button"
            className="primary-button"
            disabled={submitting || approved || plan.tasks.length === 0}
            onClick={onAccept}
          >
            {executionBusy ? 'Executing...' : approved ? 'Execution response received' : 'Approve & execute plan'}
          </button>
          <button type="button" className="secondary-button" disabled={submitting} onClick={dismiss}>
            Dismiss
          </button>
        </div>
      </div>

      {executionError ? <p className="feedback-error" role="alert">{executionError}</p> : null}

      <div className="work-plan-summary">
        <div>
          <span className="meta-label">Objective</span>
          <p>{plan.objective}</p>
        </div>
        <div>
          <span className="meta-label">Rationale</span>
          <p>{plan.rationale || 'No rationale provided.'}</p>
        </div>
        <div>
          <span className="meta-label">Proposed tasks</span>
          <p>{plan.tasks.length}</p>
        </div>
      </div>

      {approved ? (
        <p className="feedback-message" role="status">
          The backend processed the approved plan. Review each task outcome below; generated drafts are not saved until accepted.
        </p>
      ) : null}

      {validationPending ? (
        <p className="feedback-warning" role="status">
          Local edits have not been validated by the backend capability registry. Approval submits this final plan for validation; unsupported tasks will be reported.
        </p>
      ) : null}

      <div className="section-header-row">
        <h4>Tasks</h4>
        <button
          type="button"
          className="secondary-button"
          disabled={submitting || approved || plan.tasks.length >= 5}
          onClick={() => {
            setTaskDraft(createTaskDraft());
            setFormError('');
          }}
        >
          Add task
        </button>
      </div>

      {plan.tasks.length === 0 ? <p className="empty-inline">No tasks in this WorkPlan.</p> : null}
      <div className="proposal-task-list">
        {plan.tasks.map((task) => (
          <article className="proposal-task-card" key={task.task_id}>
            {taskDraft?.task_id === task.task_id ? (
              <TaskEditor
                key={taskDraft.task_id}
                task={taskDraft}
                error={formError}
                busy={submitting}
                onCancel={() => setTaskDraft(null)}
                onSubmit={saveTask}
              />
            ) : (
              <>
                <div className="proposal-task-heading">
                  <h5>{task.title}</h5>
                  <span className="tag">{task.task_id}</span>
                </div>
                <p><strong>Action:</strong> {task.action} <span aria-hidden="true">·</span> <strong>Capability:</strong> {task.capability}</p>
                <p><strong>Target:</strong> {task.target_type}{task.target_id != null ? ` #${task.target_id}` : ''}</p>
                <p><strong>Intent:</strong> {task.intent || 'Not specified.'}</p>
                <p><strong>Expected output:</strong> {task.expected_output || 'Not specified.'}</p>
                <div>
                  <strong>Completion criteria</strong>
                  <ul>
                    {task.completion_criteria.map((criterion, index) => (
                      <li key={`${task.task_id}-criterion-${index}`}>{criterion}</li>
                    ))}
                  </ul>
                </div>
                <div className="action-row">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={submitting || approved}
                    onClick={() => {
                      setTaskDraft(createTaskDraft(task));
                      setFormError('');
                    }}
                  >
                    Edit task
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    disabled={submitting || approved}
                    onClick={() => onPlanChange(removeWorkPlanTask(plan, task.task_id), true)}
                  >
                    Remove task
                  </button>
                </div>
              </>
            )}
          </article>
        ))}
      </div>

      {taskDraft && taskDraft.task_id === '' ? (
        <TaskEditor
          task={taskDraft}
          error={formError}
          busy={submitting}
          isNew
          onCancel={() => setTaskDraft(null)}
          onSubmit={saveTask}
        />
      ) : null}

      <form className="work-plan-revision-form" onSubmit={requestChanges}>
        <label htmlFor="work-plan-feedback">Request AI changes</label>
        <textarea
          id="work-plan-feedback"
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          rows={3}
          placeholder="Describe what should change in this WorkPlan."
          disabled={submitting || approved}
        />
        <button type="submit" className="secondary-button" disabled={submitting || approved || !feedback.trim()}>
          {busy ? 'Requesting changes...' : 'Request changes'}
        </button>
      </form>
    </section>
  );
}

function TaskEditor({ task, error, busy, isNew = false, onCancel, onSubmit }) {
  return (
    <form className="editor-form work-plan-task-editor" onSubmit={onSubmit}>
      {isNew ? (
        <label>Task ID<input name="task_id" defaultValue={task.task_id} placeholder="task-5" /></label>
      ) : (
        <label>Task ID<input value={task.task_id} disabled readOnly /></label>
      )}
      <label>Title<input name="title" required defaultValue={task.title} /></label>
      <label>Action
        <select name="action" defaultValue={task.action}>
          {actions.map((action) => <option key={action} value={action}>{action}</option>)}
        </select>
      </label>
      <label>Capability<input name="capability" defaultValue={task.capability} placeholder="Registered capability name" required /></label>
      <label>Target type
        <select name="target_type" defaultValue={task.target_type}>
          {targetTypes.map((targetType) => <option key={targetType} value={targetType}>{targetType}</option>)}
        </select>
      </label>
      <label>Target ID<input name="target_id" type="number" min="1" defaultValue={task.target_id} /></label>
      <label>Intent<textarea name="intent" required defaultValue={task.intent} /></label>
      <label>Expected output<textarea name="expected_output" required defaultValue={task.expected_output} /></label>
      <label>Completion criteria<textarea name="completion_criteria" required defaultValue={task.completion_criteria} /></label>
      <p className="meta-label">Capability/action/target compatibility is checked by the backend when the WorkPlan is revised. Local edits do not run tasks.</p>
      {error ? <p className="feedback-error" role="alert">{error}</p> : null}
      <div className="action-row">
        <button type="submit" className="primary-button" disabled={busy}>{isNew ? 'Add task' : 'Save task'}</button>
        <button type="button" className="secondary-button" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
