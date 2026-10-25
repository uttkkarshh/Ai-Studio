import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { executeProjectAiPlan, sendProjectAiMessage } from '../api/ai';
import { createProjectFinding, deleteFinding, getProjectFindings, updateFinding } from '../api/findings';
import { createProjectPart, deleteProjectPart, getProjectParts, updateProjectPart } from '../api/parts';
import { deleteProject, getProject, updateProject } from '../api/projects';
import { createProjectSource, deleteProjectSource, getProjectSources, updateProjectSource } from '../api/sources';
import { acceptScriptDraft, createScriptDraft } from '../api/scripts';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import PageHeader from '../components/ui/PageHeader';
import DraftResults from '../components/DraftResults';
import WorkPlanProposal from '../components/WorkPlanProposal';
import {
  parseAiResponse,
  toWorkPlanProposalPayload,
} from '../workPlan';

const tabs = ['overview', 'parts', 'sources', 'findings', 'assets'];

function formatDate(value) {
  return new Date(value).toLocaleString();
}

function jsonValue(value) {
  return JSON.stringify(value ?? null, null, 2);
}

function idList(values) {
  return values.map(Number);
}

export default function ProjectWorkspacePage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [initialLocationPathname] = useState(() => location.pathname);
  const [initialAiResponse] = useState(() => location.state?.initialAiResponse ?? null);
  const [initialParsedAiResponse] = useState(
    () => (initialAiResponse ? parseAiResponse(initialAiResponse) : null),
  );
  const [project, setProject] = useState(null);
  const [parts, setParts] = useState([]);
  const [sources, setSources] = useState([]);
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [editingProject, setEditingProject] = useState(false);
  const [partForm, setPartForm] = useState(null);
  const [sourceForm, setSourceForm] = useState(null);
  const [findingForm, setFindingForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [mutationMessage, setMutationMessage] = useState('');
  const [mutationError, setMutationError] = useState('');
  const [aiInput, setAiInput] = useState('');
  const [aiDisplayMessage, setAiDisplayMessage] = useState(
    () => (initialParsedAiResponse?.type === 'work_plan' ? '' : initialParsedAiResponse?.message || ''),
  );
  const [aiError, setAiError] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [proposal, setProposal] = useState(
    () => (initialParsedAiResponse?.type === 'work_plan' ? initialParsedAiResponse.workPlan : null),
  );
  const [proposalStatus, setProposalStatus] = useState(
    () => (initialParsedAiResponse?.type === 'work_plan' ? 'awaiting_approval' : 'proposed'),
  );
  const [proposalNeedsValidation, setProposalNeedsValidation] = useState(false);
  const [executionBusy, setExecutionBusy] = useState(false);
  const [executionError, setExecutionError] = useState('');
  const [executionState, setExecutionState] = useState('');
  const [draftReviews, setDraftReviews] = useState([]);
  const executionInProgress = useRef(false);
  const nextReviewId = useRef(1);

  const loadProjectData = useCallback(async () => {
    try {
      const [projectData, partsData, sourcesData, findingsData] = await Promise.all([
        getProject(projectId),
        getProjectParts(projectId),
        getProjectSources(projectId),
        getProjectFindings(projectId),
      ]);

      setProject(projectData);
      setError('');
      setParts(partsData);
      setSources(sourcesData);
      setFindings(findingsData);
    } catch (loadError) {
      console.error(`Project ${projectId} failed to load:`, loadError);
      setError(loadError.message || 'Unable to load project.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      getProjectParts(projectId),
      getProjectSources(projectId),
      getProjectFindings(projectId),
    ]).then(([projectData, partsData, sourcesData, findingsData]) => {
      if (!active) return;
      setProject(projectData);
      setParts(partsData);
      setSources(sourcesData);
      setFindings(findingsData);
      setError('');
    }).catch((loadError) => {
      if (active) setError(loadError.message || 'Unable to load project.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    if (initialAiResponse) navigate(initialLocationPathname, { replace: true, state: {} });
  }, [initialAiResponse, initialLocationPathname, navigate]);

  const stats = useMemo(
    () => [
      { label: 'Parts', value: parts.length },
      { label: 'Sources', value: sources.length },
      { label: 'Findings', value: findings.length },
      { label: 'Assets', value: 'API unavailable' },
    ],
    [parts.length, sources.length, findings.length],
  );

  const beginMutation = () => {
    setBusy(true);
    setMutationMessage('');
    setMutationError('');
  };

  const finishMutation = (message) => {
    setMutationMessage(message);
    setBusy(false);
  };

  const failMutation = (mutationError) => {
    setMutationError(mutationError.message || 'The request failed.');
    setBusy(false);
  };

  async function submitProject(event) {
    event.preventDefault();
    beginMutation();
    try {
      const form = new FormData(event.currentTarget);
      await updateProject(projectId, {
        name: form.get('name'),
        description: form.get('description') || null,
        objective: form.get('objective') || null,
        initial_input: form.get('initial_input') || null,
        initial_script: form.get('initial_script') || null,
      });
      setEditingProject(false);
      await loadProjectData();
      finishMutation('Project updated.');
    } catch (submitError) {
      failMutation(submitError);
    }
  }

  async function sendAiMessage(message, mode = 'message') {
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      setAiError('Please enter a message for the project AI.');
      return false;
    }

    setAiBusy(true);
    setAiError('');
    try {
      const payload = {
        message: trimmedMessage,
        scope: 'project',
        part_id: null,
        current_proposal: proposal?.type === 'work_plan'
          ? toWorkPlanProposalPayload(proposal)
          : null,
      };

      const response = await sendProjectAiMessage(projectId, payload);
      const parsedResponse = parseAiResponse(response);
      if (parsedResponse.type === 'work_plan') {
        setProposal(parsedResponse.workPlan);
        setProposalStatus(mode === 'revision' ? 'revised' : 'awaiting_approval');
        setProposalNeedsValidation(false);
        setExecutionError('');
        setAiDisplayMessage('');
      } else {
        setAiDisplayMessage(parsedResponse.message);
      }
      setAiInput('');
      return parsedResponse.type === 'work_plan';
    } catch (submitError) {
      setAiError(submitError.message || 'Unable to contact the project AI.');
      return false;
    } finally {
      setAiBusy(false);
    }
  }

  async function handleAiSubmit(event) {
    event.preventDefault();
    await sendAiMessage(aiInput, proposal?.type === 'work_plan' ? 'revision' : 'message');
  }

  function handleLocalPlanChange(updatedPlan, needsValidation) {
    setProposal(updatedPlan);
    setProposalStatus('revised');
    setProposalNeedsValidation(needsValidation);
    setAiError('');
    setExecutionError('');
  }

  function dismissProposal() {
    setProposal(null);
    setProposalStatus('proposed');
    setProposalNeedsValidation(false);
  }

  async function acceptProposal() {
    if (!proposal || executionInProgress.current) return;
    executionInProgress.current = true;
    setExecutionBusy(true);
    setExecutionError('');
    setExecutionState('Executing accepted plan...');
    try {
      const planPayload = toWorkPlanProposalPayload(proposal).data;
      const response = await executeProjectAiPlan(projectId, {
        plan: planPayload,
        scope: 'project',
        part_id: null,
        user_request: proposal.objective,
      });
      if (!response || !Array.isArray(response.tasks) || !['drafts_ready', 'needs_attention', 'failed'].includes(response.status)) {
        throw new Error('The execution endpoint returned an invalid response. The plan remains available for review.');
      }

      const draftCount = response.tasks.filter((result) => result.status === 'draft_ready' && result.draft != null).length;
      const failedCount = response.tasks.filter((result) => result.status === 'failed').length;
      const attentionCount = response.tasks.filter((result) => result.status === 'needs_clarification').length;
      const workflowState = draftCount > 0 && (failedCount > 0 || attentionCount > 0)
        ? failedCount > 0
          ? 'Partial execution failure: successful drafts and failed tasks are both shown below.'
          : 'Drafts are ready, and other tasks need clarification. Review each task outcome below.'
        : failedCount > 0
          ? 'Execution failed. No task produced a reviewable draft.'
          : attentionCount > 0
            ? 'Execution needs attention. Review the task clarification questions below.'
            : 'Drafts ready for review. Nothing has been saved to the project yet.';

      const reviewId = nextReviewId.current;
      nextReviewId.current += 1;
      setDraftReviews((reviews) => [...reviews, {
        id: reviewId,
        plan: proposal,
        status: workflowState,
        results: response.tasks,
        persistence: {},
      }]);
      setProposalStatus('approved');
      setExecutionState(workflowState);
    } catch (submitError) {
      setExecutionError(
        `${submitError.message || 'Unable to execute the approved plan.'} Your edited plan is preserved; correct any invalid capabilities or references and submit again when ready.`,
      );
      setExecutionState('Execution failed before draft results were returned.');
    } finally {
      executionInProgress.current = false;
      setExecutionBusy(false);
    }
  }

  function updateReview(reviewId, updater) {
    setDraftReviews((reviews) => reviews.map((review) => (
      review.id === reviewId ? updater(review) : review
    )));
  }

  function updateReviewDraft(reviewId, taskId, draft, metadata = {}) {
    updateReview(reviewId, (review) => ({
      ...review,
      results: review.results.map((result) => (
        result.task_id === taskId ? { ...result, draft } : result
      )),
      persistence: {
        ...review.persistence,
        [taskId]: { ...review.persistence[taskId], ...metadata },
      },
    }));
  }

  function rejectReviewDraft(reviewId, taskId) {
    updateReview(reviewId, (review) => ({
      ...review,
      results: review.results.filter((result) => result.task_id !== taskId),
    }));
  }

  async function persistReviewDraft(reviewId, result, draft, savedState) {
    let scriptDraftId = savedState.draftId;
    const setPersistence = (updates) => updateReview(reviewId, (review) => {
      const persistence = {
        ...review.persistence,
        [result.task_id]: { ...review.persistence[result.task_id], ...updates },
      };
      const hasPersisted = Object.values(persistence).some((item) => item.status === 'persisted');
      const hasSavedDraft = Object.values(persistence).some((item) => item.status === 'saved_draft');
      const status = hasPersisted
        ? 'One or more accepted drafts have been saved to project records.'
        : hasSavedDraft
          ? 'A Script Draft is saved but still needs acceptance as a Script revision.'
          : review.status;
      return { ...review, persistence, status };
    });
    setPersistence({ status: 'saving', error: '' });
    try {
      if (result.target_type === 'part') {
        const savedPart = await createProjectPart(projectId, draft);
        setParts((current) => [...current, savedPart]);
      } else if (result.target_type === 'finding') {
        const savedFinding = await createProjectFinding(projectId, draft);
        setFindings((current) => [...current, savedFinding]);
      } else if (result.target_type === 'source') {
        const savedSource = await createProjectSource(projectId, draft);
        setSources((current) => [...current, savedSource]);
      } else if (result.target_type === 'script_draft') {
        if (!scriptDraftId) {
          const savedDraft = await createScriptDraft(savedState.partId, draft);
          scriptDraftId = savedDraft.id;
          setPersistence({ status: 'saved_draft', draftId: scriptDraftId, error: '' });
        }
        await acceptScriptDraft(scriptDraftId);
      } else {
        throw new Error(`Cannot persist unsupported draft target "${result.target_type}".`);
      }
      setPersistence({ status: 'persisted', error: '' });
    } catch (persistError) {
      setPersistence({
        status: result.target_type === 'script_draft' && scriptDraftId ? 'saved_draft' : 'error',
        ...(scriptDraftId ? { draftId: scriptDraftId } : {}),
        error: persistError.message || 'The backend did not confirm draft persistence.',
      });
    }
  }

  async function requestPlanChanges(feedback) {
    if (!feedback.trim()) return false;
    return sendAiMessage(feedback, 'revision');
  }

  async function submitPart(event) {
    event.preventDefault();
    beginMutation();
    try {
      const form = new FormData(event.currentTarget);
      const payload = {
        title: form.get('title'),
        objective: form.get('objective') || null,
        description: form.get('description') || null,
        status: form.get('status'),
        position: Number(form.get('position')),
      };
      if (partForm.id) await updateProjectPart(projectId, partForm.id, payload);
      else await createProjectPart(projectId, payload);
      setPartForm(null);
      await loadProjectData();
      finishMutation(partForm.id ? 'Part updated.' : 'Part created.');
    } catch (submitError) {
      failMutation(submitError);
    }
  }

  async function submitSource(event) {
    event.preventDefault();
    beginMutation();
    try {
      const form = new FormData(event.currentTarget);
      const metadataText = form.get('metadata');
      const payload = {
        title: form.get('title'),
        url: form.get('url') || null,
        source_type: form.get('source_type'),
        content: form.get('content') || null,
        metadata: metadataText ? JSON.parse(metadataText) : null,
        part_ids: idList(form.getAll('part_ids')),
      };
      if (sourceForm.id) await updateProjectSource(projectId, sourceForm.id, payload);
      else await createProjectSource(projectId, payload);
      setSourceForm(null);
      await loadProjectData();
      finishMutation(sourceForm.id ? 'Source updated.' : 'Source created.');
    } catch (submitError) {
      failMutation(submitError instanceof SyntaxError ? new Error('Metadata must be valid JSON.') : submitError);
    }
  }

  async function submitFinding(event) {
    event.preventDefault();
    beginMutation();
    try {
      const form = new FormData(event.currentTarget);
      const contentText = form.get('content');
      const payload = {
        heading: form.get('heading'),
        content: contentText ? JSON.parse(contentText) : null,
        created_by_type: form.get('created_by_type'),
        status: form.get('status'),
        part_ids: idList(form.getAll('part_ids')),
        source_ids: idList(form.getAll('source_ids')),
      };
      if (findingForm.id) await updateFinding(findingForm.id, payload);
      else await createProjectFinding(projectId, payload);
      setFindingForm(null);
      await loadProjectData();
      finishMutation(findingForm.id ? 'Finding updated.' : 'Finding created.');
    } catch (submitError) {
      failMutation(submitError instanceof SyntaxError ? new Error('Finding content must be valid JSON.') : submitError);
    }
  }

  async function runDelete(label, operation, afterDelete, confirmation) {
    if (!window.confirm(confirmation || `${label} This action permanently deletes this record.`)) return;
    beginMutation();
    try {
      await operation();
      await afterDelete();
      finishMutation(`${label.replace('Delete ', '')} deleted.`);
    } catch (deleteError) {
      failMutation(deleteError);
    }
  }

  if (loading) {
    return <LoadingState message="Loading project workspace..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadProjectData} />;
  }

  if (!project) {
    return <EmptyState title="Project not found." message="The selected project could not be loaded." />;
  }

  return (
    <>
      <PageHeader
        title={project.name}
        description={project.description || 'Project workspace overview.'}
        action={(
          <div className="action-row">
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setEditingProject((value) => !value)}>
              {editingProject ? 'Cancel edit' : 'Edit project'}
            </button>
            <button
              type="button"
              className="danger-button"
              disabled={busy}
              onClick={() => runDelete('Delete project?', () => deleteProject(projectId), () => navigate('/'), `Delete "${project.name}" and all child records? This action is permanent.`)}
            >
              Delete project
            </button>
          </div>
        )}
      />

      {mutationMessage ? <p className="feedback-message" role="status">{mutationMessage}</p> : null}
      {mutationError ? <p className="feedback-error" role="alert">{mutationError}</p> : null}

      {editingProject ? (
        <form className="card-panel editor-form" onSubmit={submitProject}>
          <h3>Edit project</h3>
          <label>Name<input name="name" required defaultValue={project.name} /></label>
          <label>Description<textarea name="description" defaultValue={project.description || ''} /></label>
          <label>Objective<textarea name="objective" required defaultValue={project.objective || ''} /></label>
          <label>Initial input<textarea name="initial_input" required defaultValue={project.initial_input || ''} /></label>
          <label>Initial script<textarea name="initial_script" defaultValue={project.initial_script || ''} /></label>
          <button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save project'}</button>
        </form>
      ) : null}

      <section className="card-panel">
        <h3>Project AI</h3>
        <form onSubmit={handleAiSubmit} className="editor-form">
          <label>
            {proposal ? 'Ask the AI about this project or describe a plan revision...' : 'Tell AI what you want to do with this project...'}
            <textarea
              value={aiInput}
              onChange={(event) => setAiInput(event.target.value)}
              rows={4}
              placeholder={proposal ? 'Describe the changes you want in natural language.' : 'Outline the project goal, constraints, or source review.'}
            />
          </label>
          <div className="action-row">
            <button type="submit" className="primary-button" disabled={aiBusy || !aiInput.trim()}>
              {aiBusy ? 'Sending...' : proposal ? 'Send request' : 'Send'}
            </button>
          </div>
        </form>
        {aiError ? <p className="feedback-error" role="alert">{aiError}</p> : null}
        {aiDisplayMessage ? (
          <div className="ai-response-panel" role="status">
            <p>{aiDisplayMessage}</p>
          </div>
        ) : null}
      </section>

      {proposal?.type === 'work_plan' ? (
        <WorkPlanProposal
          plan={proposal}
          status={proposalStatus}
          validationPending={proposalNeedsValidation}
          busy={aiBusy}
          executionBusy={executionBusy}
          executionConfirmed={proposalStatus === 'approved'}
          executionError={executionError}
          onPlanChange={handleLocalPlanChange}
          onAccept={acceptProposal}
          onDismiss={dismissProposal}
          onRequestChanges={requestPlanChanges}
        />
      ) : null}

      {executionState === 'Executing accepted plan...' ? (
        <p className="feedback-message" role="status">{executionState}</p>
      ) : null}
      {draftReviews.map((review) => (
        <DraftResults
          key={review.id}
          results={review.results}
          plan={review.plan}
          status={review.status}
          parts={parts}
          persistence={review.persistence}
          onAccept={(result, draft, savedState) => persistReviewDraft(review.id, result, draft, savedState)}
          onReject={(taskId) => rejectReviewDraft(review.id, taskId)}
          onUpdateDraft={(taskId, draft, metadata) => updateReviewDraft(review.id, taskId, draft, metadata)}
        />
      ))}

      <nav className="workspace-tabs" aria-label="Project sections">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            className={`tab-button ${activeTab === tab ? 'tab-button-active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </nav>

      {activeTab === 'overview' ? (
        <>
          <section className="workspace-overview card-panel">
            <div className="overview-grid">
              <div>
                <h2>Project overview</h2>
                <p>{project.objective || 'No project objective has been set yet.'}</p>
              </div>
              <div className="meta-list">
                <div>
                  <span className="meta-label">Created</span>
                  <strong>{formatDate(project.created_at)}</strong>
                </div>
                <div>
                  <span className="meta-label">Updated</span>
                  <strong>{formatDate(project.updated_at)}</strong>
                </div>
                <div>
                  <span className="meta-label">Initial input</span>
                  <strong>{project.initial_input || 'Not provided'}</strong>
                </div>
              </div>
            </div>
            <details className="debug-details">
              <summary>View raw project JSON</summary>
              <pre>{jsonValue(project)}</pre>
            </details>
          </section>

          <section className="stat-grid">
            {stats.map((stat) => (
              <div key={stat.label} className="stat-card card-panel">
                <span className="stat-label">{stat.label}</span>
                <strong>{stat.value}</strong>
              </div>
            ))}
          </section>
        </>
      ) : null}

      {activeTab === 'parts' ? (
        <section className="card-panel">
          <div className="section-header-row">
            <h3>Parts</h3>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setPartForm({ title: '', objective: '', description: '', status: 'planned', position: parts.length })}>Create part</button>
          </div>

          {partForm ? (
            <form className="editor-form" onSubmit={submitPart}>
              <h4>{partForm.id ? 'Edit part' : 'Create part'}</h4>
              <label>Title<input name="title" required defaultValue={partForm.title} /></label>
              <label>Objective<textarea name="objective" defaultValue={partForm.objective || ''} /></label>
              <label>Description<textarea name="description" defaultValue={partForm.description || ''} /></label>
              <label>Status<input name="status" required defaultValue={partForm.status} /></label>
              <label>Position<input name="position" type="number" required defaultValue={partForm.position} /></label>
              <div className="action-row">
                <button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save part'}</button>
                <button type="button" className="secondary-button" onClick={() => setPartForm(null)}>Cancel</button>
              </div>
            </form>
          ) : null}

          {parts.length === 0 ? (
            <p className="empty-inline">No parts have been created for this project yet.</p>
          ) : (
            <ul className="resource-list">
              {parts.map((part) => (
                <li key={part.id} className="resource-item">
                  <div>
                    <Link to={`/projects/${projectId}/parts/${part.id}`} className="resource-link">
                      <strong>{part.title}</strong>
                    </Link>
                    <div className="resource-meta">{part.status} • Position {part.position}</div>
                  </div>
                  <div className="tag-list">
                    <span className="tag">{part.id}</span>
                    <button type="button" className="secondary-button" disabled={busy} onClick={() => setPartForm(part)}>Edit</button>
                    <button type="button" className="danger-button" disabled={busy} onClick={() => runDelete('Delete part?', () => deleteProjectPart(projectId, part.id), loadProjectData)}>Delete</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {activeTab === 'sources' ? (
        <section className="card-panel">
          <div className="section-header-row">
            <h3>Sources</h3>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setSourceForm({ title: '', url: '', source_type: 'document', content: '', metadata: '{}', part_ids: [] })}>Create source</button>
          </div>

          {sourceForm ? (
            <form className="editor-form" key={`source-${sourceForm.id || 'new'}`} onSubmit={submitSource}>
              <h4>{sourceForm.id ? 'Edit source' : 'Create source'}</h4>
              <label>Title<input name="title" required defaultValue={sourceForm.title} /></label>
              <label>URL<input name="url" type="url" defaultValue={sourceForm.url || ''} /></label>
              <label>Source type<input name="source_type" required defaultValue={sourceForm.source_type} /></label>
              <label>Content<textarea name="content" defaultValue={sourceForm.content || ''} /></label>
              <label>Metadata JSON<textarea name="metadata" defaultValue={sourceForm.metadata ?? jsonValue(sourceForm.metadata)} /></label>
              <fieldset><legend>Associated Parts</legend>
                {parts.map((part) => <label className="check-option" key={part.id}><input type="checkbox" name="part_ids" value={part.id} defaultChecked={sourceForm.part_ids?.includes(part.id) || sourceForm.part_ids?.includes(String(part.id))} />{part.title}</label>)}
              </fieldset>
              <div className="action-row">
                <button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save source'}</button>
                <button type="button" className="secondary-button" onClick={() => setSourceForm(null)}>Cancel</button>
              </div>
            </form>
          ) : null}

          {sources.length === 0 ? (
            <p className="empty-inline">No sources are attached to this project.</p>
          ) : (
            <ul className="resource-list">
              {sources.map((source) => (
                <li key={source.id} className="resource-item stacked-item">
                  <div>
                    <strong>{source.title}</strong>
                    <div className="resource-meta">{source.source_type}{source.url ? ` · ${source.url}` : ''} · Parts: {source.part_ids.length}</div>
                  </div>
                  <div className="tag-list">
                    <span className="tag">{source.id}</span>
                    <button type="button" className="secondary-button" disabled={busy} onClick={() => setSourceForm({ ...source, metadata: jsonValue(source.metadata) })}>Edit</button>
                    <button type="button" className="danger-button" disabled={busy} onClick={() => runDelete('Delete source?', () => deleteProjectSource(projectId, source.id), loadProjectData)}>Delete</button>
                  </div>
                  <details className="debug-details"><summary>View raw source JSON</summary><pre>{jsonValue(source)}</pre></details>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {activeTab === 'findings' ? (
        <section className="card-panel">
          <div className="section-header-row">
            <h3>Findings</h3>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setFindingForm({ heading: '', content: '', created_by_type: 'user', status: 'draft', part_ids: [], source_ids: [] })}>Create finding</button>
          </div>

          {findingForm ? (
            <form className="editor-form" key={`finding-${findingForm.id || 'new'}`} onSubmit={submitFinding}>
              <h4>{findingForm.id ? 'Edit finding' : 'Create finding'}</h4>
              <label>Heading<input name="heading" required defaultValue={findingForm.heading} /></label>
              <label>Content JSON<textarea name="content" defaultValue={typeof findingForm.content === 'string' ? findingForm.content : jsonValue(findingForm.content)} /></label>
              <label>Created by<select name="created_by_type" defaultValue={findingForm.created_by_type}><option value="user">user</option><option value="ai">ai</option><option value="imported">imported</option></select></label>
              <label>Status<select name="status" defaultValue={findingForm.status}><option value="draft">draft</option><option value="active">active</option><option value="archived">archived</option></select></label>
              <fieldset><legend>Associated Parts</legend>
                {parts.map((part) => <label className="check-option" key={part.id}><input type="checkbox" name="part_ids" value={part.id} defaultChecked={findingForm.part_ids?.includes(part.id) || findingForm.part_ids?.includes(String(part.id))} />{part.title}</label>)}
              </fieldset>
              <fieldset><legend>Supporting Sources</legend>
                {sources.map((source) => <label className="check-option" key={source.id}><input type="checkbox" name="source_ids" value={source.id} defaultChecked={findingForm.source_ids?.includes(source.id) || findingForm.source_ids?.includes(String(source.id))} />{source.title}</label>)}
              </fieldset>
              <div className="action-row">
                <button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save finding'}</button>
                <button type="button" className="secondary-button" onClick={() => setFindingForm(null)}>Cancel</button>
              </div>
            </form>
          ) : null}

          {findings.length === 0 ? (
            <p className="empty-inline">No findings exist for this project yet.</p>
          ) : (
            <ul className="resource-list">
              {findings.map((finding) => (
                <li key={finding.id} className="resource-item stacked-item">
                  <div>
                    <strong>{finding.heading}</strong>
                    <div className="resource-meta">{finding.status} • {finding.created_by_type}</div>
                    <div className="resource-meta">Parts: {finding.part_ids.map((id) => parts.find((part) => part.id === id)?.title || id).join(', ') || 'None'} · Sources: {finding.source_ids.map((id) => sources.find((source) => source.id === id)?.title || id).join(', ') || 'None'}</div>
                  </div>
                  <div className="tag-list">
                    <span className="tag">{finding.id}</span>
                    <button type="button" className="secondary-button" disabled={busy} onClick={() => setFindingForm({ ...finding, content: jsonValue(finding.content) })}>Edit</button>
                    <button type="button" className="danger-button" disabled={busy} onClick={() => runDelete('Delete finding?', () => deleteFinding(finding.id), loadProjectData)}>Delete</button>
                  </div>
                  <details className="debug-details"><summary>View raw finding JSON</summary><pre>{jsonValue(finding)}</pre></details>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {activeTab === 'assets' ? (
        <section className="card-panel warning-panel">
          <h3>Assets</h3>
          <p>
            The backend does not currently expose an asset API surface, so this domain is intentionally
            unavailable in the current working backend contract.
          </p>
        </section>
      ) : null}
    </>
  );
}
