import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { executeProjectAiPlan, sendProjectAiMessage } from '../api/ai';
import { getProject } from '../api/projects';
import { createPartCommit, createProjectPart, deleteProjectPart, getPartCommit, getPartCommits, getProjectPart, restorePartCommit, updateProjectPart } from '../api/parts';
import { createProjectFinding, getProjectFindings, updateFinding } from '../api/findings';
import { createProjectSource, getProjectSources, updateProjectSource } from '../api/sources';
import { acceptScriptDraft, createScriptDraft, getPartScript, getPartScriptDrafts, getScriptDraft, getScriptRevision, getScriptRevisions, restoreScriptRevision, updateScriptDraft } from '../api/scripts';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import PageHeader from '../components/ui/PageHeader';
import DraftResults from '../components/DraftResults';
import WorkPlanProposal from '../components/WorkPlanProposal';
import { parseAiResponse, toWorkPlanProposalPayload } from '../workPlan';

function safeJson(value) {
  return JSON.stringify(value, null, 2);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

export default function PartWorkspacePage() {
  const { projectId, partId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [part, setPart] = useState(null);
  const [sources, setSources] = useState([]);
  const [findings, setFindings] = useState([]);
  const [commits, setCommits] = useState([]);
  const [script, setScript] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [scriptRevisions, setScriptRevisions] = useState([]);
  const [partFormOpen, setPartFormOpen] = useState(false);
  const [draftForm, setDraftForm] = useState(null);
  const [commitMessage, setCommitMessage] = useState('');
  const [commitScriptRevisionId, setCommitScriptRevisionId] = useState('');
  const [selectedPartRevision, setSelectedPartRevision] = useState(null);
  const [selectedScriptRevision, setSelectedScriptRevision] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scriptError, setScriptError] = useState('');
  const [busy, setBusy] = useState(false);
  const [mutationMessage, setMutationMessage] = useState('');
  const [mutationError, setMutationError] = useState('');
  const [aiInput, setAiInput] = useState('');
  const [aiDisplayMessage, setAiDisplayMessage] = useState('');
  const [aiError, setAiError] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [aiProposal, setAiProposal] = useState(null);
  const [proposalStatus, setProposalStatus] = useState('proposed');
  const [proposalNeedsValidation, setProposalNeedsValidation] = useState(false);
  const [executionBusy, setExecutionBusy] = useState(false);
  const [executionError, setExecutionError] = useState('');
  const [executionState, setExecutionState] = useState('');
  const [draftReviews, setDraftReviews] = useState([]);
  const executionInProgress = useRef(false);
  const nextReviewId = useRef(1);

  const relatedSources = useMemo(
    () => sources.filter((source) => source.part_ids.includes(Number(partId))),
    [sources, partId],
  );

  const relatedFindings = useMemo(
    () => findings.filter((finding) => finding.part_ids.includes(Number(partId))),
    [findings, partId],
  );

  const orderedCommits = useMemo(
    () => [...commits].sort((first, second) => first.revision_number - second.revision_number),
    [commits],
  );

  const loadPartData = useCallback(async () => {
    try {
      const [projectData, partData, sourcesData, findingsData, commitsData, draftsData] = await Promise.all([
        getProject(projectId),
        getProjectPart(projectId, partId),
        getProjectSources(projectId),
        getProjectFindings(projectId),
        getPartCommits(partId),
        getPartScriptDrafts(partId),
      ]);

      setProject(projectData);
      setPart(partData);
      setError('');
      setSources(sourcesData);
      setFindings(findingsData);
      setCommits(commitsData);
      setDrafts(draftsData);

      try {
        setScriptError('');
        const scriptData = await getPartScript(partId);
        if (!scriptData) {
          setScript(null);
          setScriptRevisions([]);
          setCommitScriptRevisionId('');
          return;
        }
        const revisions = await getScriptRevisions(scriptData.id);
        setScript(scriptData);
        setScriptRevisions(revisions);
        setCommitScriptRevisionId(scriptData.current_revision_id != null ? String(scriptData.current_revision_id) : (revisions[0] ? String(revisions[0].id) : ''));
      } catch (scriptError) {
        setScript(null);
        setScriptRevisions([]);
        setScriptError(scriptError.message || 'Unable to load official Script data.');
      }
    } catch (loadError) {
      console.error(`Part ${partId} failed to load:`, loadError);
      setError(loadError.message || 'Unable to load part workspace.');
      throw loadError;
    } finally {
      setLoading(false);
    }
  }, [projectId, partId]);

  useEffect(() => {
    let active = true;
    const loadInitialPartData = async () => {
      try {
        const [projectData, partData, sourcesData, findingsData, commitsData, draftsData] = await Promise.all([
          getProject(projectId),
          getProjectPart(projectId, partId),
          getProjectSources(projectId),
          getProjectFindings(projectId),
          getPartCommits(partId),
          getPartScriptDrafts(partId),
        ]);
        if (!active) return;
        setProject(projectData);
        setPart(partData);
        setSources(sourcesData);
        setFindings(findingsData);
        setCommits(commitsData);
        setDrafts(draftsData);
        setError('');

        try {
          setScriptError('');
          const scriptData = await getPartScript(partId);
          if (!scriptData) {
            if (active) {
              setScript(null);
              setScriptRevisions([]);
              setCommitScriptRevisionId('');
            }
            return;
          }
          const revisions = await getScriptRevisions(scriptData.id);
          if (active) {
            setScript(scriptData);
            setScriptRevisions(revisions);
            setCommitScriptRevisionId(scriptData.current_revision_id != null ? String(scriptData.current_revision_id) : (revisions[0] ? String(revisions[0].id) : ''));
          }
        } catch (scriptFailure) {
          if (!active) return;
          setScript(null);
          setScriptRevisions([]);
          setScriptError(scriptFailure.message || 'Unable to load official Script data.');
        }
      } catch (loadError) {
        if (active) setError(loadError.message || 'Unable to load part workspace.');
      } finally {
        if (active) setLoading(false);
      }
    };
    loadInitialPartData();
    return () => { active = false; };
  }, [projectId, partId]);

  const runMutation = async (operation, successText) => {
    setBusy(true);
    setMutationMessage('');
    setMutationError('');
    try {
      await operation();
      await loadPartData();
      setMutationMessage(successText);
      return true;
    } catch (mutationFailure) {
      setMutationError(mutationFailure.message || 'The request failed.');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const submitPart = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    runMutation(() => updateProjectPart(projectId, partId, {
      title: form.get('title'),
      objective: form.get('objective') || null,
      description: form.get('description') || null,
      status: form.get('status'),
      position: Number(form.get('position')),
    }), 'Part updated.').then((saved) => { if (saved) setPartFormOpen(false); });
  };

  const submitDraft = async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const contentText = form.get('content');
      const payload = {
        title: form.get('title') || null,
        content: contentText ? JSON.parse(contentText) : null,
        created_by_type: form.get('created_by_type'),
      };
      const saved = await runMutation(
        () => draftForm.id ? updateScriptDraft(draftForm.id, payload) : createScriptDraft(partId, payload),
        draftForm.id ? 'Draft updated.' : 'Draft created.',
      );
      if (saved) setDraftForm(null);
    } catch (submitError) {
      setMutationError(submitError instanceof SyntaxError ? 'Draft content must be valid JSON.' : submitError.message);
    }
  };

  const acceptDraft = (draft) => {
    runMutation(() => acceptScriptDraft(draft.id), `Draft "${draft.title || draft.id}" accepted into the official Script.`);
  };

  const openPartRevision = async (revisionId) => {
    setMutationError('');
    try {
      setSelectedPartRevision(await getPartCommit(partId, revisionId));
    } catch (detailError) {
      setMutationError(detailError.message || 'Unable to load Part revision.');
    }
  };

  const openScriptRevision = async (scriptId, revisionId) => {
    setMutationError('');
    try {
      setSelectedScriptRevision(await getScriptRevision(scriptId, revisionId));
    } catch (detailError) {
      setMutationError(detailError.message || 'Unable to load Script revision.');
    }
  };

  const submitCommit = (event) => {
    event.preventDefault();
    const message = commitMessage.trim();
    const selectedRevisionId = Number(commitScriptRevisionId);

    if (!message) {
      setMutationError('Please enter a commit message before creating a Part revision.');
      return;
    }

    if (!script || !script.current_revision_id || Number.isNaN(selectedRevisionId)) {
      setMutationError('There is no current Script revision to attach to this Part commit. Accept a Script draft first.');
      return;
    }

    runMutation(
      () => createPartCommit(partId, {
        commit_message: message,
        script_revision_id: selectedRevisionId,
      }),
      'Part committed.',
    ).then((saved) => {
      if (saved) {
        setCommitMessage('');
        setCommitScriptRevisionId(String(script.current_revision_id));
      }
    });
  };

  const restorePartRevision = (revision) => {
    if (!window.confirm('Restore this Part revision? Restoring creates a new Part revision. Existing history is preserved.')) return;
    runMutation(() => restorePartCommit(partId, revision.id), `Restored Part revision ${revision.revision_number} as a new revision.`);
  };

  const restoreScript = (revision) => {
    if (!script) return;
    if (!window.confirm('Restore this Script revision? This creates a new revision. Existing history is not deleted.')) return;
    runMutation(() => restoreScriptRevision(script.id, revision.id), `Restored Script revision ${revision.revision_number} as a new revision.`);
  };

  const sendPartAiMessage = async (message, mode = 'message') => {
    if (!message.trim()) {
      setAiError('Please enter a message for the part AI.');
      return false;
    }

    setAiBusy(true);
    setAiError('');
    try {
      const response = await sendProjectAiMessage(projectId, {
        message: message.trim(),
        scope: 'part',
        part_id: Number(partId),
        current_proposal: aiProposal?.type === 'work_plan'
          ? toWorkPlanProposalPayload(aiProposal)
          : null,
      });
      const parsedResponse = parseAiResponse(response);
      if (parsedResponse.type === 'work_plan') {
        setAiProposal(parsedResponse.workPlan);
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
      setAiError(submitError.message || 'Unable to contact the part AI.');
      return false;
    } finally {
      setAiBusy(false);
    }
  };

  const handleAiSubmit = async (event) => {
    event.preventDefault();
    await sendPartAiMessage(aiInput, aiProposal ? 'revision' : 'message');
  };

  const updateLocalAiPlan = (updatedPlan, needsValidation) => {
    setAiProposal(updatedPlan);
    setProposalStatus('revised');
    setProposalNeedsValidation(needsValidation);
    setExecutionError('');
  };

  const executePartPlan = async () => {
    if (!aiProposal || executionInProgress.current) return;
    executionInProgress.current = true;
    setExecutionBusy(true);
    setExecutionError('');
    setExecutionState('Executing accepted plan...');
    try {
      const response = await executeProjectAiPlan(projectId, {
        plan: toWorkPlanProposalPayload(aiProposal).data,
        scope: 'part',
        part_id: Number(partId),
        user_request: aiProposal.objective,
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
      const persistence = Object.fromEntries(
        response.tasks
          .filter((result) => result.target_type === 'script_draft')
          .map((result) => [result.task_id, { partId: Number(partId) }]),
      );
      setDraftReviews((reviews) => [...reviews, {
        id: reviewId,
        plan: aiProposal,
        status: workflowState,
        results: response.tasks,
        persistence,
      }]);
      setProposalStatus('approved');
      setExecutionState(workflowState);
    } catch (submitError) {
      setExecutionError(
        `${submitError.message || 'Unable to execute the accepted plan.'} Your edited plan is preserved; correct any invalid capabilities or references and submit again when ready.`,
      );
      setExecutionState('Execution failed before draft results were returned.');
    } finally {
      executionInProgress.current = false;
      setExecutionBusy(false);
    }
  };

  const updateReview = (reviewId, updater) => {
    setDraftReviews((reviews) => reviews.map((review) => (
      review.id === reviewId ? updater(review) : review
    )));
  };

  const updateReviewDraft = (reviewId, taskId, draft, metadata = {}) => {
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
  };

  const rejectReviewDraft = (reviewId, taskId) => {
    updateReview(reviewId, (review) => ({
      ...review,
      results: review.results.filter((result) => result.task_id !== taskId),
    }));
  };

  const persistReviewDraft = async (reviewId, result, draft, savedState) => {
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
        await createProjectPart(projectId, draft);
      } else if (result.target_type === 'finding') {
        const savedFinding = await createProjectFinding(projectId, draft);
        setFindings((current) => [...current, savedFinding]);
      } else if (result.target_type === 'source') {
        const savedSource = await createProjectSource(projectId, draft);
        setSources((current) => [...current, savedSource]);
      } else if (result.target_type === 'script_draft') {
        if (!scriptDraftId) {
          const savedDraft = await createScriptDraft(partId, draft);
          scriptDraftId = savedDraft.id;
          setPersistence({ status: 'saved_draft', draftId: scriptDraftId, partId: Number(partId), error: '' });
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
  };

  const changeAssociation = (entity, id, attached) => {
    if (entity === 'source') {
      const source = sources.find((item) => item.id === id);
      const partIds = attached
        ? [...source.part_ids, Number(partId)]
        : source.part_ids.filter((linkedId) => linkedId !== Number(partId));
      return runMutation(() => updateProjectSource(projectId, id, { part_ids: partIds }), attached ? 'Source attached.' : 'Source detached.');
    }
    const finding = findings.find((item) => item.id === id);
    const partIds = attached
      ? [...finding.part_ids, Number(partId)]
      : finding.part_ids.filter((linkedId) => linkedId !== Number(partId));
    return runMutation(() => updateFinding(id, { part_ids: partIds }), attached ? 'Finding attached.' : 'Finding detached.');
  };

  const deletePart = () => {
    if (!window.confirm(`Delete "${part.title}"? This permanently deletes this Part and its history.`)) return;
    runMutation(() => deleteProjectPart(projectId, partId), 'Part deleted.').then((deleted) => { if (deleted) navigate(`/projects/${projectId}`); });
  };

  const currentRevision = scriptRevisions.find((revision) => revision.id === script?.current_revision_id);
  const commitRevisionOptions = scriptRevisions.filter((revision) => revision.script_id === script?.id);
  const effectiveCommitScriptRevisionId = script?.current_revision_id != null
    ? Number(script.current_revision_id)
    : (Number(commitScriptRevisionId) || '');

  if (loading) {
    return <LoadingState message="Loading part workspace..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => { setLoading(true); loadPartData().catch(() => {}); }} />;
  }

  if (!part) {
    return (
      <div className="state-panel empty-panel">
        <p className="state-title">Part not found</p>
        <p>The requested part could not be loaded from the project.</p>
        <Link to={`/projects/${projectId}`} className="primary-button inline-link-button">
          Back to project
        </Link>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={part.title}
        description={part.objective || part.description || 'Part workspace overview.'}
        action={<div className="action-row">
          <Link to={`/projects/${projectId}`} className="secondary-button inline-link-button">Back to project</Link>
          <button type="button" className="secondary-button" disabled={busy} onClick={() => setPartFormOpen((value) => !value)}>Edit part</button>
          <button type="button" className="danger-button" disabled={busy} onClick={deletePart}>Delete part</button>
        </div>}
      />

      {mutationMessage ? <p className="feedback-message" role="status">{mutationMessage}</p> : null}
      {mutationError ? <p className="feedback-error" role="alert">{mutationError}</p> : null}

      <section className="card-panel">
        <h3>Part AI</h3>
        <form onSubmit={handleAiSubmit} className="editor-form">
          <label>
            Tell AI what you want to do with this part...
            <textarea
              value={aiInput}
              onChange={(event) => setAiInput(event.target.value)}
              rows={4}
              placeholder="Research this topic..."
            />
          </label>
          <div className="action-row">
            <button type="submit" className="primary-button" disabled={aiBusy || !aiInput.trim()}>
              {aiBusy ? 'Sending...' : 'Send'}
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
      {aiProposal?.type === 'work_plan' ? (
        <WorkPlanProposal
          plan={aiProposal}
          status={proposalStatus}
          validationPending={proposalNeedsValidation}
          busy={aiBusy}
          executionBusy={executionBusy}
          executionConfirmed={proposalStatus === 'approved'}
          executionError={executionError}
          onPlanChange={updateLocalAiPlan}
          onAccept={executePartPlan}
          onDismiss={() => {
            setAiProposal(null);
            setProposalStatus('proposed');
            setProposalNeedsValidation(false);
          }}
          onRequestChanges={(feedback) => sendPartAiMessage(feedback, 'revision')}
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
          parts={[part]}
          persistence={review.persistence}
          onAccept={(result, draft, savedState) => persistReviewDraft(review.id, result, draft, savedState)}
          onReject={(taskId) => rejectReviewDraft(review.id, taskId)}
          onUpdateDraft={(taskId, draft, metadata) => updateReviewDraft(review.id, taskId, draft, metadata)}
        />
      ))}

      <nav className="workspace-tabs part-section-nav" aria-label="Part sections">
        <a className="tab-button tab-link" href="#part-overview">Overview</a>
        <a className="tab-button tab-link" href="#part-sources">Sources</a>
        <a className="tab-button tab-link" href="#part-script">Script</a>
        <a className="tab-button tab-link" href="#part-history">History</a>
      </nav>

      {partFormOpen ? (
        <form className="card-panel editor-form" onSubmit={submitPart}>
          <h3>Edit current Part</h3>
          <label>Title<input name="title" required defaultValue={part.title} /></label>
          <label>Objective<textarea name="objective" defaultValue={part.objective || ''} /></label>
          <label>Description<textarea name="description" defaultValue={part.description || ''} /></label>
          <label>Status<input name="status" required defaultValue={part.status} /></label>
          <label>Position<input name="position" type="number" required defaultValue={part.position} /></label>
          <div className="action-row"><button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save part'}</button><button type="button" className="secondary-button" onClick={() => setPartFormOpen(false)}>Cancel</button></div>
        </form>
      ) : null}

      <section className="stat-grid">
        <div className="stat-card card-panel">
          <span className="stat-label">Status</span>
          <strong>{part.status}</strong>
        </div>
        <div className="stat-card card-panel">
          <span className="stat-label">Position</span>
          <strong>{part.position}</strong>
        </div>
        <div className="stat-card card-panel">
          <span className="stat-label">Linked sources</span>
          <strong>{relatedSources.length}</strong>
        </div>
        <div className="stat-card card-panel">
          <span className="stat-label">Linked findings</span>
          <strong>{relatedFindings.length}</strong>
        </div>
      </section>

      <section className="detail-grid">
        <div className="card-panel compact-panel" id="part-overview">
          <h3>Part overview</h3>
          <dl className="info-list">
            <div>
              <dt>Project</dt>
              <dd>{project?.name || 'Project'}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(part.created_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatDate(part.updated_at)}</dd>
            </div>
            <div>
              <dt>Objective</dt>
              <dd>{part.objective || 'No objective recorded.'}</dd>
            </div>
          </dl>
          <details className="debug-details">
            <summary>View raw part JSON</summary>
            <pre>{safeJson(part)}</pre>
          </details>
        </div>

        <div className="card-panel compact-panel" id="part-sources">
          <h3>Sources</h3>
          <p className="resource-meta">Sources remain project-level records and may be attached to multiple Parts.</p>
          {sources.length === 0 ? <p className="empty-inline">No project Sources are available.</p> : (
            <ul className="resource-list compact-list">{sources.map((source) => {
              const attached = source.part_ids.includes(Number(partId));
              return <li key={source.id} className="resource-item stacked-item">
                <div><strong>{source.title}</strong><div className="resource-meta">{source.source_type}{source.url ? ` · ${source.url}` : ''}</div></div>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => changeAssociation('source', source.id, !attached)}>{attached ? 'Detach source' : 'Attach source'}</button>
                <details className="debug-details"><summary>View raw source JSON</summary><pre>{safeJson(source)}</pre></details>
              </li>;
            })}</ul>
          )}
        </div>

        <div className="card-panel compact-panel">
          <h3>Findings</h3>
          <p className="resource-meta">Project-level Findings can be associated with multiple Parts.</p>
          {findings.length === 0 ? <p className="empty-inline">No project Findings are available.</p> : (
            <ul className="resource-list compact-list">{findings.map((finding) => {
              const attached = finding.part_ids.includes(Number(partId));
              return <li key={finding.id} className="resource-item stacked-item">
                <div><strong>{finding.heading}</strong><div className="resource-meta">{finding.status} · {finding.created_by_type}</div></div>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => changeAssociation('finding', finding.id, !attached)}>{attached ? 'Detach finding' : 'Attach finding'}</button>
                <details className="debug-details"><summary>View raw finding JSON</summary><pre>{safeJson(finding)}</pre></details>
              </li>;
            })}</ul>
          )}
        </div>
      </section>

      <section className="detail-grid">
        <div className="card-panel compact-panel" id="part-script">
          <div className="section-header-row"><h3>Script drafts</h3><button type="button" className="secondary-button" disabled={busy} onClick={() => setDraftForm({ title: '', content: '', created_by_type: 'user' })}>Create draft</button></div>
          {draftForm ? <form className="editor-form" onSubmit={submitDraft} key={`draft-${draftForm.id || 'new'}`}>
            <h4>{draftForm.id ? 'Edit draft' : 'Create draft'}</h4>
            <label>Title<input name="title" disabled={draftForm.status === 'accepted'} defaultValue={draftForm.title || ''} /></label>
            <label>Content JSON<textarea name="content" disabled={draftForm.status === 'accepted'} defaultValue={typeof draftForm.content === 'string' ? draftForm.content : safeJson(draftForm.content)} /></label>
            <label>Created by<select name="created_by_type" disabled={draftForm.status === 'accepted'} defaultValue={draftForm.created_by_type || 'user'}><option value="user">user</option><option value="ai">ai</option><option value="imported">imported</option></select></label>
            <div className="action-row">{draftForm.status !== 'accepted' ? <button className="primary-button" disabled={busy}>{busy ? 'Saving...' : 'Save draft'}</button> : <span className="resource-meta">Accepted drafts are read-only.</span>}<button type="button" className="secondary-button" onClick={() => setDraftForm(null)}>Close</button></div>
          </form> : null}
          {drafts.length === 0 ? <p className="empty-inline">No Script drafts exist for this Part.</p> : <ul className="resource-list compact-list">{drafts.map((draft) => <li key={draft.id} className="resource-item stacked-item">
            <div><strong>{draft.title || `Draft ${draft.id}`}</strong><div className="resource-meta">{draft.status} · {draft.created_by_type} · Created {formatDate(draft.created_at)} · Updated {formatDate(draft.updated_at)}</div></div>
            <div className="action-row">
              <button type="button" className="secondary-button" onClick={async () => { try { setDraftForm(await getScriptDraft(draft.id)); } catch (draftError) { setMutationError(draftError.message); } }}>View / edit</button>
              {draft.status !== 'accepted' ? <button type="button" className="primary-button" disabled={busy} onClick={() => acceptDraft(draft)}>Accept draft</button> : null}
            </div>
            <details className="debug-details"><summary>View draft content and raw JSON</summary><pre>{safeJson(draft.content)}</pre><pre>{safeJson(draft)}</pre></details>
          </li>)}</ul>}

          <hr />
          <h3>Official Script</h3>
          {script ? <>
            <p className="resource-meta">Script ID: {script.id} · Current revision: {currentRevision ? `Revision ${currentRevision.revision_number}` : 'None'}</p>
            {currentRevision ? <div className="snapshot-block"><strong>Current Revision {currentRevision.revision_number}</strong><pre>{safeJson(currentRevision.content)}</pre></div> : <p className="empty-inline">No current Script revision.</p>}
            <details className="debug-details"><summary>View raw Script JSON</summary><pre>{safeJson(script)}</pre></details>
          </> : scriptError
            ? <p className="feedback-error" role="alert">Official Script unavailable: {scriptError}</p>
            : <p className="empty-inline">No official Script exists. Accept a draft to create one.</p>}
          <h4>Script revisions</h4>
          {scriptRevisions.length === 0 ? <p className="empty-inline">No Script revisions yet.</p> : <ul className="resource-list compact-list">{scriptRevisions.map((revision) => <li key={revision.id} className="resource-item stacked-item">
            <div><strong>Revision {revision.revision_number}{revision.id === script?.current_revision_id ? ' · Current' : ''}</strong><div className="resource-meta">{revision.commit_message} · {revision.created_by_type} · {formatDate(revision.created_at)}</div><div className="resource-meta">Source draft: {revision.source_draft_id ?? 'None'}</div></div>
            <div className="action-row"><button type="button" className="secondary-button" onClick={() => openScriptRevision(revision.script_id, revision.id)}>Open revision</button><button type="button" className="secondary-button" disabled={busy} onClick={() => restoreScript(revision)}>Restore this revision</button></div>
            <details className="debug-details"><summary>View raw ScriptRevision JSON</summary><pre>{safeJson(revision)}</pre></details>
          </li>)}</ul>}
          {selectedScriptRevision ? <div className="snapshot-block"><div className="section-header-row"><h4>Script Revision {selectedScriptRevision.revision_number}</h4><button type="button" className="secondary-button" onClick={() => setSelectedScriptRevision(null)}>Close</button></div><p>{selectedScriptRevision.commit_message} · {selectedScriptRevision.created_by_type} · {formatDate(selectedScriptRevision.created_at)}</p><pre>{safeJson(selectedScriptRevision.content)}</pre><details className="debug-details"><summary>View raw ScriptRevision JSON</summary><pre>{safeJson(selectedScriptRevision)}</pre></details></div> : null}
        </div>

        <div className="card-panel compact-panel">
          <h3 id="part-history">Part history</h3>
          <form className="editor-form" onSubmit={submitCommit}>
            <label>Commit message<input value={commitMessage} required onChange={(event) => setCommitMessage(event.target.value)} /></label>
            {script && script.current_revision_id ? (
              <label>
                Script revision for this commit
                <select value={effectiveCommitScriptRevisionId} onChange={(event) => setCommitScriptRevisionId(event.target.value)}>
                  {commitRevisionOptions.length === 0 ? (
                    <option value="">No Script revisions available</option>
                  ) : (
                    commitRevisionOptions.map((revision) => (
                      <option key={revision.id} value={revision.id}>Revision {revision.revision_number} (ID {revision.id})</option>
                    ))
                  )}
                </select>
              </label>
            ) : (
              <p className="empty-inline">No current Script revision is available yet. Accept a draft to create one before committing the Part.</p>
            )}
            <button type="submit" className="primary-button" disabled={busy || !commitMessage.trim() || !script || !script.current_revision_id || !commitScriptRevisionId}>{busy ? 'Committing...' : 'Commit Part'}</button>
          </form>
          {commits.length === 0 ? (
            <p className="empty-inline">No part revisions have been captured yet.</p>
          ) : (
            <ul className="resource-list compact-list">
              {orderedCommits.map((commit) => (
                <li key={commit.id} className="resource-item stacked-item">
                  <div>
                    <strong>Revision {commit.revision_number}</strong>
                    <div className="resource-meta">{commit.commit_message}</div>
                    <div className="resource-meta">{commit.created_by} • {formatDate(commit.created_at)}</div>
                  </div>
                  <div className="action-row"><button type="button" className="secondary-button" onClick={() => openPartRevision(commit.id)}>Open snapshot</button><button type="button" className="secondary-button" disabled={busy} onClick={() => restorePartRevision(commit)}>Restore this revision</button></div>
                  <details className="debug-details">
                    <summary>View raw PartRevision JSON</summary>
                    <pre>{safeJson(commit)}</pre>
                  </details>
                </li>
              ))}
            </ul>
          )}
          {selectedPartRevision ? <div className="snapshot-block">
            <div className="section-header-row"><h4>Historical Part Revision {selectedPartRevision.revision_number}</h4><button type="button" className="secondary-button" onClick={() => setSelectedPartRevision(null)}>Close</button></div>
            <p className="snapshot-label">HISTORICAL PART REVISION · CURRENT PART IS SHOWN ABOVE</p>
            <dl className="info-list">
              <div><dt>Title</dt><dd>{selectedPartRevision.title}</dd></div>
              <div><dt>Objective</dt><dd>{selectedPartRevision.objective || 'None'}</dd></div>
              <div><dt>Description</dt><dd>{selectedPartRevision.description || 'None'}</dd></div>
              <div><dt>Status / Position</dt><dd>{selectedPartRevision.status} / {selectedPartRevision.position}</dd></div>
              <div><dt>Sources</dt><dd>{(selectedPartRevision.sources || []).map((id) => sources.find((source) => source.id === id)?.title || `Source ${id}`).join(', ') || 'None'}</dd></div>
              <div><dt>Assets</dt><dd>{(selectedPartRevision.assets || []).join(', ') || 'None; Asset API unavailable'}</dd></div>
              <div><dt>Commit message</dt><dd>{selectedPartRevision.commit_message}</dd></div>
              <div><dt>Created by / timestamp</dt><dd>{selectedPartRevision.created_by} · {formatDate(selectedPartRevision.created_at)}</dd></div>
              <div>
                <dt>PartRevision → ScriptRevision</dt>
                <dd>
                  {selectedPartRevision.script_revision_id ? (
                    <button type="button" className="resource-link button-link" onClick={() => openScriptRevision(script?.id, selectedPartRevision.script_revision_id)}>
                      Inspect linked Script revision {scriptRevisions.find((revision) => revision.id === selectedPartRevision.script_revision_id)?.revision_number ?? `ID ${selectedPartRevision.script_revision_id}`}
                    </button>
                  ) : 'None'}
                </dd>
              </div>
              <div><dt>script_revision_id</dt><dd>{selectedPartRevision.script_revision_id ?? 'None'}</dd></div>
            </dl>
            <details className="debug-details"><summary>View raw PartRevision JSON</summary><pre>{safeJson(selectedPartRevision)}</pre></details>
          </div> : null}
        </div>
      </section>
      <section className="card-panel warning-panel"><h3>Relationships and Assets</h3><p>Part Relationship endpoints and Asset CRUD/association endpoints are not present in the live backend API, so these workflows are unavailable.</p></section>
    </>
  );
}
