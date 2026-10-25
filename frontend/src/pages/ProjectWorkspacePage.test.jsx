// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProjectWorkspacePage from './ProjectWorkspacePage';

const api = vi.hoisted(() => ({
  sendProjectAiMessage: vi.fn(),
  executeProjectAiPlan: vi.fn(),
  createProjectFinding: vi.fn(),
  deleteFinding: vi.fn(),
  getProjectFindings: vi.fn(),
  updateFinding: vi.fn(),
  createProjectPart: vi.fn(),
  deleteProjectPart: vi.fn(),
  getProjectParts: vi.fn(),
  updateProjectPart: vi.fn(),
  deleteProject: vi.fn(),
  getProject: vi.fn(),
  updateProject: vi.fn(),
  createProjectSource: vi.fn(),
  deleteProjectSource: vi.fn(),
  getProjectSources: vi.fn(),
  updateProjectSource: vi.fn(),
  createScriptDraft: vi.fn(),
  acceptScriptDraft: vi.fn(),
}));

vi.mock('../api/ai', () => ({
  executeProjectAiPlan: api.executeProjectAiPlan,
  sendProjectAiMessage: api.sendProjectAiMessage,
}));
vi.mock('../api/findings', () => ({
  createProjectFinding: api.createProjectFinding,
  deleteFinding: api.deleteFinding,
  getProjectFindings: api.getProjectFindings,
  updateFinding: api.updateFinding,
}));
vi.mock('../api/parts', () => ({
  createProjectPart: api.createProjectPart,
  deleteProjectPart: api.deleteProjectPart,
  getProjectParts: api.getProjectParts,
  updateProjectPart: api.updateProjectPart,
}));
vi.mock('../api/projects', () => ({
  deleteProject: api.deleteProject,
  getProject: api.getProject,
  updateProject: api.updateProject,
}));
vi.mock('../api/sources', () => ({
  createProjectSource: api.createProjectSource,
  deleteProjectSource: api.deleteProjectSource,
  getProjectSources: api.getProjectSources,
  updateProjectSource: api.updateProjectSource,
}));
vi.mock('../api/scripts', () => ({
  createScriptDraft: api.createScriptDraft,
  acceptScriptDraft: api.acceptScriptDraft,
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  api.getProject.mockResolvedValue({
    id: 42,
    name: 'Coastal resilience',
    description: '',
    objective: 'Review coastal flood resilience.',
    initial_input: null,
    initial_script: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  });
  api.getProjectParts.mockResolvedValue([]);
  api.getProjectSources.mockResolvedValue([]);
  api.getProjectFindings.mockResolvedValue([]);
});

function makePlan(title = 'Research coastal risk') {
  return {
    objective: 'Review coastal flood resilience.',
    rationale: 'Evidence is needed before drafting.',
    tasks: [
      {
        task_id: 'research-risk',
        title,
        action: 'research',
        capability: 'research',
        target_type: 'project',
        target_id: null,
        intent: 'Gather evidence on coastal flood risks.',
        expected_output: 'Relevant evidence and source candidates.',
        completion_criteria: ['Evidence addresses the project objective.'],
      },
    ],
  };
}

function executionResponse(tasks, status = 'drafts_ready') {
  return {
    project_id: 42,
    status,
    objective: 'Review coastal flood resilience.',
    tasks,
  };
}

function partResult(taskId = 'research-risk') {
  return {
    task_id: taskId,
    target_type: 'part',
    status: 'draft_ready',
    target_id: null,
    validation: { schema_valid: true, warnings: [] },
    requires_user_approval: true,
    clarification_questions: [],
    error: null,
    draft: { title: 'Coastal risk', objective: 'Assess risks.', description: null, status: 'planned', position: 0 },
  };
}

function renderWorkspace(initialAiResponse) {
  return render(
    <MemoryRouter initialEntries={[{
      pathname: '/projects/42',
      state: initialAiResponse ? { initialAiResponse } : {},
    }]}
    >
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProjectWorkspacePage WorkPlan response flow', () => {
  it('renders a WorkPlan as task cards instead of displaying the API JSON', async () => {
    renderWorkspace({
      action: { action: 'create_plan', reason: 'A plan was requested.' },
      message: 'I prepared a work plan for review.',
      proposal: { type: 'work_plan', data: makePlan() },
    });

    expect(await screen.findByRole('heading', { name: 'Research coastal risk' })).toBeTruthy();
    expect(screen.getByText('Evidence addresses the project objective.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Proposed WorkPlan' })).toBeTruthy();
    expect(document.querySelector('.ai-response-panel')).toBeNull();
    expect(screen.queryByText(/"task_id"/)).toBeNull();
    expect(document.querySelectorAll('.proposal-task-card')).toHaveLength(1);
  });

  it('shows conversational responses as ordinary messages and does not render task cards', async () => {
    renderWorkspace({
      action: { action: 'answer', reason: 'A direct answer.' },
      message: 'The project studies coastal resilience.',
      proposal: null,
    });

    expect(await screen.findByText('The project studies coastal resilience.')).toBeTruthy();
    expect(document.querySelector('.proposal-task-card')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Proposed WorkPlan' })).toBeNull();
  });

  it('shows safe fallbacks for malformed and legacy proposals', async () => {
    const responses = [
      {
        proposal: { type: 'work_plan', data: { objective: 'Missing tasks', tasks: [] } },
      },
      {
        proposal: { type: 'project_plan', data: { title: 'Old plan', parts: [] } },
      },
    ];

    for (const response of responses) {
      const { unmount } = renderWorkspace(response);
      expect(await screen.findByRole('status')).toBeTruthy();
      expect(document.querySelector('.proposal-task-card')).toBeNull();
      unmount();
    }
  });

  it('sends revision feedback with the current WorkPlan and replaces it only with a valid revision', async () => {
    api.sendProjectAiMessage.mockResolvedValueOnce({
      action: { action: 'revise_plan', reason: 'Revising the proposal.' },
      message: 'I prepared a revised work plan.',
      proposal: { type: 'work_plan', data: makePlan('Compare coastal risk indicators') },
    });
    renderWorkspace({
      message: 'Initial plan.',
      proposal: { type: 'work_plan', data: makePlan() },
    });

    expect(await screen.findByRole('heading', { name: 'Proposed WorkPlan' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Request AI changes'), {
      target: { value: 'Compare coastal risk indicators.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Request changes' }));

    expect(await screen.findByRole('heading', { name: 'Compare coastal risk indicators' })).toBeTruthy();
    expect(api.sendProjectAiMessage).toHaveBeenCalledWith(
      '42',
      expect.objectContaining({
        message: 'Compare coastal risk indicators.',
        scope: 'project',
        current_proposal: expect.objectContaining({ type: 'work_plan' }),
      }),
    );
  });

  it('preserves the current proposal after a failed revision request', async () => {
    api.sendProjectAiMessage.mockRejectedValueOnce(new Error('Connection dropped.'));
    renderWorkspace({
      message: 'Initial plan.',
      proposal: { type: 'work_plan', data: makePlan() },
    });

    expect(await screen.findByRole('heading', { name: 'Proposed WorkPlan' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Request AI changes'), {
      target: { value: 'Add an adaptation assessment.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Request changes' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Connection dropped.');
    expect(screen.getByRole('heading', { name: 'Research coastal risk' })).toBeTruthy();
  });

  it('submits the final edited plan to the execution API contract and displays unsaved drafts', async () => {
    api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([partResult()]));
    renderWorkspace({
      message: 'Initial plan.',
      proposal: { type: 'work_plan', data: makePlan() },
    });

    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Edit task' }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Compare coastal indicators' } });
    fireEvent.change(screen.getByLabelText('Intent'), { target: { value: 'Compare regional flood-risk indicators.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save task' }));
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect(await screen.findByRole('heading', { name: 'Draft Results' })).toBeTruthy();
    expect(api.executeProjectAiPlan).toHaveBeenCalledWith('42', {
      plan: {
        objective: 'Review coastal flood resilience.',
        rationale: 'Evidence is needed before drafting.',
        tasks: [{
          task_id: 'research-risk',
          title: 'Compare coastal indicators',
          action: 'research',
          capability: 'research',
          target_type: 'project',
          target_id: null,
          intent: 'Compare regional flood-risk indicators.',
          expected_output: 'Relevant evidence and source candidates.',
          completion_criteria: ['Evidence addresses the project objective.'],
        }],
      },
      scope: 'project',
      part_id: null,
      user_request: 'Review coastal flood resilience.',
    });
    expect(screen.getByText('Each generated draft is saved only after you accept it; generation alone does not persist project data.')).toBeTruthy();
    expect(api.createProjectPart).not.toHaveBeenCalled();
  });

  it('preserves the edited plan and reports backend validation errors', async () => {
    api.executeProjectAiPlan.mockRejectedValueOnce(new Error('HTTP 422: Unsupported capability: research'));
    renderWorkspace({
      proposal: { type: 'work_plan', data: makePlan() },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Edit task' }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Keep my edited title' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save task' }));
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect((await screen.findByRole('alert')).textContent).toContain('HTTP 422: Unsupported capability');
    expect(screen.getByRole('heading', { name: 'Keep my edited title' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Approve & execute plan' }).disabled).toBe(false);
    expect(document.querySelector('.draft-results-panel')).toBeNull();
  });

  it('preserves the plan and surfaces network failures without retrying', async () => {
    api.executeProjectAiPlan.mockRejectedValueOnce(new Error('Network request failed for POST /api/projects/42/ai/execute'));
    renderWorkspace({
      proposal: { type: 'work_plan', data: makePlan() },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Network request failed');
    expect(screen.getByRole('heading', { name: 'Research coastal risk' })).toBeTruthy();
    expect(api.executeProjectAiPlan).toHaveBeenCalledOnce();
  });

  it('prevents duplicate execution requests while the backend is processing the plan', async () => {
    let finishExecution;
    api.executeProjectAiPlan.mockImplementationOnce(() => new Promise((resolve) => {
      finishExecution = resolve;
    }));
    renderWorkspace({
      proposal: { type: 'work_plan', data: makePlan() },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    const executeButton = screen.getByRole('button', { name: 'Approve & execute plan' });
    fireEvent.click(executeButton);
    fireEvent.click(executeButton);

    expect(api.executeProjectAiPlan).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Executing...' }).disabled).toBe(true);
    finishExecution(executionResponse([partResult()]));
    expect(await screen.findByRole('heading', { name: 'Draft Results' })).toBeTruthy();
  });

  it('shows successful and failed task outcomes separately in a partial execution', async () => {
    api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([
      partResult(),
      {
        task_id: 'find-conflicts',
        target_type: 'finding',
        status: 'failed',
        target_id: null,
        validation: { schema_valid: false, warnings: [] },
        requires_user_approval: true,
        clarification_questions: [],
        error: 'The generated draft could not be validated.',
        draft: null,
      },
    ], 'failed'));
    renderWorkspace({
      proposal: {
        type: 'work_plan',
        data: {
          ...makePlan(),
          tasks: [
            ...makePlan().tasks,
            { ...makePlan().tasks[0], task_id: 'find-conflicts', title: 'Find conflicts' },
          ],
        },
      },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect(await screen.findByText(/Partial execution failure/)).toBeTruthy();
    expect(screen.getAllByRole('heading', { name: 'Research coastal risk' })).toHaveLength(2);
    const failedCard = document.querySelectorAll('.draft-result-card')[1];
    expect(failedCard.textContent).toContain('failed');
    expect(failedCard.textContent).toContain('The generated draft could not be validated.');
    expect(failedCard.querySelector('button')).toBeNull();
  });

  it('persists a Part only after Accept Draft succeeds', async () => {
    api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([partResult()]));
    api.createProjectPart.mockResolvedValueOnce({ id: 90, title: 'Coastal risk' });
    renderWorkspace({
      proposal: { type: 'work_plan', data: makePlan() },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));
    await screen.findByRole('heading', { name: 'Draft Results' });
    expect(screen.queryByText('Saved and accepted by the backend.')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Accept Draft' }));

    expect(await screen.findByText('Saved and accepted by the backend.')).toBeTruthy();
    expect(api.createProjectPart).toHaveBeenCalledWith('42', partResult().draft);
  });

  it('persists Findings and Sources through their existing creation endpoints only after acceptance', async () => {
    const cases = [
      {
        target: 'finding',
        taskTitle: 'Create a finding',
        draft: { heading: 'Risk finding', content: { evidence: ['Observed'] }, created_by_type: 'ai', status: 'draft', part_ids: [], source_ids: [] },
        save: api.createProjectFinding,
      },
      {
        target: 'source',
        taskTitle: 'Create a source',
        draft: { title: 'Coastal report', url: null, source_type: 'report', content: null, metadata: {}, part_ids: [] },
        save: api.createProjectSource,
      },
    ];

    for (const [index, draftCase] of cases.entries()) {
      draftCase.save.mockResolvedValueOnce({ id: 60 + index });
      api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([{
        task_id: `accept-${draftCase.target}`,
        target_type: draftCase.target,
        status: 'draft_ready',
        target_id: null,
        validation: { schema_valid: true, warnings: [] },
        requires_user_approval: true,
        clarification_questions: [],
        error: null,
        draft: draftCase.draft,
      }]));
      renderWorkspace({
        proposal: {
          type: 'work_plan',
          data: {
            ...makePlan(),
            tasks: [{ ...makePlan().tasks[0], task_id: `accept-${draftCase.target}`, title: draftCase.taskTitle }],
          },
        },
      });
      await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
      fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));
      await screen.findByRole('heading', { name: 'Draft Results' });
      expect(draftCase.save).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: 'Accept Draft' }));
      expect(await screen.findByText('Saved and accepted by the backend.')).toBeTruthy();
      expect(draftCase.save).toHaveBeenCalledWith('42', draftCase.draft);
      cleanup();
    }
  });

  it('saves and accepts Script Drafts using the selected Part and existing endpoints', async () => {
    api.getProjectParts.mockResolvedValueOnce([{ id: 17, title: 'Coastal risks' }]);
    api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([{
      task_id: 'script-task',
      target_type: 'script_draft',
      status: 'draft_ready',
      target_id: null,
      validation: { schema_valid: true, warnings: [] },
      requires_user_approval: true,
      clarification_questions: [],
      error: null,
      draft: { title: 'Narration', content: { scenes: ['Opening'] }, created_by_type: 'ai' },
    }]));
    api.createScriptDraft.mockResolvedValueOnce({ id: 44 });
    api.acceptScriptDraft.mockResolvedValueOnce({ id: 45, status: 'accepted' });
    renderWorkspace({
      proposal: {
        type: 'work_plan',
        data: {
          ...makePlan(),
          tasks: [{
            task_id: 'script-task',
            title: 'Draft a script',
            action: 'generate_draft',
            capability: 'generate_script_draft',
            target_type: 'script_draft',
            target_id: null,
            intent: 'Draft narration.',
            expected_output: 'A script draft.',
            completion_criteria: ['Narration follows the outline.'],
          }],
        },
      },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));
    await screen.findByRole('heading', { name: 'Draft Results' });
    const scriptCard = document.querySelector('.draft-result-card');
    expect(scriptCard.querySelectorAll('button')[1].disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Save script draft to Part'), { target: { value: '17' } });
    fireEvent.click(screen.getByRole('button', { name: 'Accept Draft' }));

    expect(await screen.findByText('Saved and accepted by the backend.')).toBeTruthy();
    expect(api.createScriptDraft).toHaveBeenCalledWith(17, {
      title: 'Narration',
      content: { scenes: ['Opening'] },
      created_by_type: 'ai',
    });
    expect(api.acceptScriptDraft).toHaveBeenCalledWith(44);
  });

  it('reports a Script Draft saved when revision acceptance fails and retries only the safe acceptance step', async () => {
    api.getProjectParts.mockResolvedValueOnce([{ id: 17, title: 'Coastal risks' }]);
    api.executeProjectAiPlan.mockResolvedValueOnce(executionResponse([{
      task_id: 'script-task',
      target_type: 'script_draft',
      status: 'draft_ready',
      target_id: null,
      validation: { schema_valid: true, warnings: [] },
      requires_user_approval: true,
      clarification_questions: [],
      error: null,
      draft: { title: 'Narration', content: { scenes: ['Opening'] }, created_by_type: 'ai' },
    }]));
    api.createScriptDraft.mockResolvedValueOnce({ id: 44 });
    api.acceptScriptDraft
      .mockRejectedValueOnce(new Error('HTTP 500: acceptance failed'))
      .mockResolvedValueOnce({ id: 45, status: 'accepted' });
    renderWorkspace({
      proposal: {
        type: 'work_plan',
        data: {
          ...makePlan(),
          tasks: [{
            task_id: 'script-task',
            title: 'Draft a script',
            action: 'generate_draft',
            capability: 'generate_script_draft',
            target_type: 'script_draft',
            target_id: null,
            intent: 'Draft narration.',
            expected_output: 'A script draft.',
            completion_criteria: ['Narration follows the outline.'],
          }],
        },
      },
    });
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));
    await screen.findByRole('heading', { name: 'Draft Results' });
    fireEvent.change(await screen.findByLabelText('Save script draft to Part'), { target: { value: '17' } });
    fireEvent.click(screen.getByRole('button', { name: 'Accept Draft' }));

    expect(await screen.findByText(/Script draft #44 is saved, but was not accepted/)).toBeTruthy();
    expect(screen.queryByText('Saved and accepted by the backend.')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Accept Script Draft' }));

    expect(await screen.findByText('Saved and accepted by the backend.')).toBeTruthy();
    expect(api.createScriptDraft).toHaveBeenCalledOnce();
    expect(api.acceptScriptDraft).toHaveBeenCalledTimes(2);
    expect(api.acceptScriptDraft).toHaveBeenLastCalledWith(44);
  });
});
