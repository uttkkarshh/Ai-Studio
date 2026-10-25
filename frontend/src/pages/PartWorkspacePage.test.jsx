// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PartWorkspacePage from './PartWorkspacePage';

const api = vi.hoisted(() => ({
  executeProjectAiPlan: vi.fn(),
  sendProjectAiMessage: vi.fn(),
  getProject: vi.fn(),
  createPartCommit: vi.fn(),
  createProjectPart: vi.fn(),
  deleteProjectPart: vi.fn(),
  getPartCommit: vi.fn(),
  getPartCommits: vi.fn(),
  getProjectPart: vi.fn(),
  restorePartCommit: vi.fn(),
  updateProjectPart: vi.fn(),
  createProjectFinding: vi.fn(),
  getProjectFindings: vi.fn(),
  updateFinding: vi.fn(),
  createProjectSource: vi.fn(),
  getProjectSources: vi.fn(),
  updateProjectSource: vi.fn(),
  acceptScriptDraft: vi.fn(),
  createScriptDraft: vi.fn(),
  getPartScript: vi.fn(),
  getPartScriptDrafts: vi.fn(),
  getScriptDraft: vi.fn(),
  getScriptRevision: vi.fn(),
  getScriptRevisions: vi.fn(),
  restoreScriptRevision: vi.fn(),
  updateScriptDraft: vi.fn(),
}));

vi.mock('../api/ai', () => ({
  executeProjectAiPlan: api.executeProjectAiPlan,
  sendProjectAiMessage: api.sendProjectAiMessage,
}));
vi.mock('../api/projects', () => ({ getProject: api.getProject }));
vi.mock('../api/parts', () => ({
  createPartCommit: api.createPartCommit,
  createProjectPart: api.createProjectPart,
  deleteProjectPart: api.deleteProjectPart,
  getPartCommit: api.getPartCommit,
  getPartCommits: api.getPartCommits,
  getProjectPart: api.getProjectPart,
  restorePartCommit: api.restorePartCommit,
  updateProjectPart: api.updateProjectPart,
}));
vi.mock('../api/findings', () => ({
  createProjectFinding: api.createProjectFinding,
  getProjectFindings: api.getProjectFindings,
  updateFinding: api.updateFinding,
}));
vi.mock('../api/sources', () => ({
  createProjectSource: api.createProjectSource,
  getProjectSources: api.getProjectSources,
  updateProjectSource: api.updateProjectSource,
}));
vi.mock('../api/scripts', () => ({
  acceptScriptDraft: api.acceptScriptDraft,
  createScriptDraft: api.createScriptDraft,
  getPartScript: api.getPartScript,
  getPartScriptDrafts: api.getPartScriptDrafts,
  getScriptDraft: api.getScriptDraft,
  getScriptRevision: api.getScriptRevision,
  getScriptRevisions: api.getScriptRevisions,
  restoreScriptRevision: api.restoreScriptRevision,
  updateScriptDraft: api.updateScriptDraft,
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  api.getProject.mockResolvedValue({ id: 42, name: 'Coastal resilience' });
  api.getProjectPart.mockResolvedValue({
    id: 17,
    project_id: 42,
    title: 'Coastal risks',
    objective: 'Assess local flood risks.',
    description: '',
    status: 'planned',
    position: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  });
  api.getProjectSources.mockResolvedValue([]);
  api.getProjectFindings.mockResolvedValue([]);
  api.getPartCommits.mockResolvedValue([]);
  api.getPartScriptDrafts.mockResolvedValue([]);
  api.getPartScript.mockResolvedValue(null);
});

function renderPartWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/projects/42/parts/17']}>
      <Routes>
        <Route path="/projects/:projectId/parts/:partId" element={<PartWorkspacePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PartWorkspacePage accepted-plan flow', () => {
  it('submits Part-scoped plans to the existing execution route and accepts the generated Script Draft', async () => {
    api.sendProjectAiMessage.mockResolvedValueOnce({
      action: { action: 'create_plan', reason: 'A Part plan was requested.' },
      message: 'I prepared a work plan for your review.',
      requires_approval: true,
      proposal: {
        type: 'work_plan',
        data: {
          objective: 'Draft narration for this Part.',
          rationale: 'The Part needs a script.',
          tasks: [{
            task_id: 'part-script',
            title: 'Draft Part narration',
            action: 'generate_draft',
            capability: 'generate_script_draft',
            target_type: 'script_draft',
            target_id: null,
            intent: 'Write narration based on this Part.',
            expected_output: 'An editable Script Draft.',
            completion_criteria: ['Narration follows the Part objective.'],
          }],
        },
      },
    });
    api.executeProjectAiPlan.mockResolvedValueOnce({
      project_id: 42,
      status: 'drafts_ready',
      objective: 'Draft narration for this Part.',
      tasks: [{
        task_id: 'part-script',
        target_type: 'script_draft',
        status: 'draft_ready',
        target_id: null,
        validation: { schema_valid: true, warnings: [] },
        requires_user_approval: true,
        clarification_questions: [],
        error: null,
        draft: { title: 'Coastal narration', content: { scenes: ['Opening'] }, created_by_type: 'ai' },
      }],
    });
    api.createScriptDraft.mockResolvedValueOnce({ id: 81 });
    api.acceptScriptDraft.mockResolvedValueOnce({ id: 82, status: 'accepted' });

    renderPartWorkspace();
    fireEvent.change(await screen.findByLabelText('Tell AI what you want to do with this part...'), {
      target: { value: 'Draft narration for this Part.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByRole('heading', { name: 'Proposed WorkPlan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect(await screen.findByRole('heading', { name: 'Draft Results' })).toBeTruthy();
    expect(api.executeProjectAiPlan).toHaveBeenCalledWith('42', {
      plan: {
        objective: 'Draft narration for this Part.',
        rationale: 'The Part needs a script.',
        tasks: [{
          task_id: 'part-script',
          title: 'Draft Part narration',
          action: 'generate_draft',
          capability: 'generate_script_draft',
          target_type: 'script_draft',
          target_id: null,
          intent: 'Write narration based on this Part.',
          expected_output: 'An editable Script Draft.',
          completion_criteria: ['Narration follows the Part objective.'],
        }],
      },
      scope: 'part',
      part_id: 17,
      user_request: 'Draft narration for this Part.',
    });
    fireEvent.click(screen.getByRole('button', { name: 'Accept Draft' }));
    expect(await screen.findByText('Saved and accepted by the backend.')).toBeTruthy();
    expect(api.createScriptDraft).toHaveBeenCalledWith('17', {
      title: 'Coastal narration',
      content: { scenes: ['Opening'] },
      created_by_type: 'ai',
    });
    expect(api.acceptScriptDraft).toHaveBeenCalledWith(81);
  });
});
