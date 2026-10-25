// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DraftResults from './DraftResults';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const taskDefinitions = [
  { task_id: 'part-task', title: 'Create a Part' },
  { task_id: 'finding-task', title: 'Record a Finding' },
  { task_id: 'source-task', title: 'Add a Source' },
  { task_id: 'script-task', title: 'Draft a Script' },
  { task_id: 'failed-task', title: 'Failed task' },
];

const results = [
  {
    task_id: 'part-task',
    target_type: 'part',
    status: 'draft_ready',
    draft: { title: 'Flood indicators', objective: 'Compare indicators.', description: null, status: 'planned', position: 0 },
    validation: { schema_valid: true, warnings: [] },
  },
  {
    task_id: 'finding-task',
    target_type: 'finding',
    status: 'draft_ready',
    draft: { heading: 'Risk varies', content: { evidence: ['A', 'B'] }, created_by_type: 'ai', status: 'draft', part_ids: [], source_ids: [] },
    validation: { schema_valid: true, warnings: [] },
  },
  {
    task_id: 'source-task',
    target_type: 'source',
    status: 'draft_ready',
    draft: { title: 'Coastal report', url: null, source_type: 'report', content: null, metadata: { publisher: 'Agency' }, part_ids: [] },
    validation: { schema_valid: true, warnings: [] },
  },
  {
    task_id: 'script-task',
    target_type: 'script_draft',
    status: 'draft_ready',
    draft: { title: 'Narration', content: [{ narration: 'Flood risk is increasing.' }], created_by_type: 'ai' },
    validation: { schema_valid: true, warnings: [] },
  },
  {
    task_id: 'failed-task',
    target_type: 'finding',
    status: 'failed',
    draft: null,
    error: 'The generated draft could not be validated.',
    validation: { schema_valid: false, warnings: [] },
  },
];

function renderResults(overrides = {}) {
  return render(
    <DraftResults
      results={results}
      plan={{ tasks: taskDefinitions }}
      status="Partial execution failure: successful drafts and failed tasks are both shown below."
      parts={[{ id: 12, title: 'Coastal risks' }]}
      persistence={{}}
      onAccept={vi.fn()}
      onReject={vi.fn()}
      onUpdateDraft={vi.fn()}
      {...overrides}
    />,
  );
}

describe('DraftResults', () => {
  it('renders all supported draft types as readable fields and keeps failures distinct', () => {
    renderResults();

    expect(screen.getByRole('heading', { name: 'Draft Results' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Create a Part' })).toBeTruthy();
    expect(screen.getByText('Part')).toBeTruthy();
    expect(screen.getAllByText('Finding')).toHaveLength(2);
    expect(screen.getByText('Source')).toBeTruthy();
    expect(screen.getByText('Script Draft')).toBeTruthy();
    expect(screen.getByText('Flood indicators')).toBeTruthy();
    expect(screen.getByText('Risk varies')).toBeTruthy();
    expect(screen.getByText('Coastal report')).toBeTruthy();
    expect(screen.getByText('Narration')).toBeTruthy();
    expect(screen.getByText('Partial execution failure: successful drafts and failed tasks are both shown below.')).toBeTruthy();
    expect(screen.getByText('The generated draft could not be validated.')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Accept Draft', exact: true })).toHaveLength(4);
    expect(screen.queryAllByRole('button', { name: 'Accept Draft' })).toHaveLength(4);
    expect(screen.getAllByRole('button', { name: 'Edit Draft', exact: true })).toHaveLength(4);
    const failedCard = screen.getByText('Failed task').closest('.draft-result-card');
    expect(failedCard.querySelector('button')).toBeNull();
  });

  it('edits structured content without flattening its JSON types and validates the target schema', () => {
    const onUpdateDraft = vi.fn();
    renderResults({ onUpdateDraft });

    fireEvent.click(screen.getAllByRole('button', { name: 'Edit Draft' })[1]);
    const editor = screen.getByLabelText('Edit Record a Finding draft JSON');
    const edited = {
      heading: 'Updated finding',
      content: { evidence: ['C'], confidence: 0.8 },
      created_by_type: 'ai',
      status: 'draft',
      part_ids: [],
      source_ids: [],
    };
    fireEvent.change(editor, { target: { value: JSON.stringify(edited) } });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft edits' }));

    expect(onUpdateDraft).toHaveBeenCalledWith('finding-task', edited);
    expect(screen.queryByLabelText('Edit Record a Finding draft JSON')).toBeNull();
  });

  it('reports invalid edits and only removes a draft after reject confirmation', () => {
    const onUpdateDraft = vi.fn();
    const onReject = vi.fn();
    const confirm = vi.fn().mockReturnValue(true);
    vi.stubGlobal('confirm', confirm);
    renderResults({ onUpdateDraft, onReject });

    fireEvent.click(screen.getAllByRole('button', { name: 'Edit Draft' })[0]);
    fireEvent.change(screen.getByLabelText('Edit Create a Part draft JSON'), {
      target: { value: JSON.stringify({ title: '', status: 'planned', position: 0 }) },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft edits' }));
    expect(screen.getAllByRole('alert').some((alert) => alert.textContent.includes('Part title is required'))).toBe(true);
    expect(onUpdateDraft).not.toHaveBeenCalled();

    fireEvent.click(screen.getAllByRole('button', { name: 'Reject Draft' })[0]);
    expect(confirm).toHaveBeenCalledOnce();
    expect(onReject).toHaveBeenCalledWith('part-task');
  });

  it('does not claim generated drafts are persisted before the persistence callback confirms them', () => {
    const onAccept = vi.fn();
    renderResults({ onAccept });

    expect(screen.getByText('Each generated draft is saved only after you accept it; generation alone does not persist project data.')).toBeTruthy();
    expect(screen.queryByText('Saved and accepted by the backend.')).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: 'Accept Draft' })[0]);
    expect(onAccept).toHaveBeenCalledWith(results[0], results[0].draft, {});
    expect(screen.queryByText('Saved and accepted by the backend.')).toBeNull();
  });

  it('requires selecting a Part before accepting a Script Draft', () => {
    const onUpdateDraft = vi.fn();
    renderResults({ onUpdateDraft });
    const scriptCard = screen.getByText('Draft a Script').closest('.draft-result-card');
    expect(scriptCard.querySelector('select').value).toBe('');
    expect(scriptCard.querySelectorAll('button')[1].disabled).toBe(true);
    fireEvent.change(scriptCard.querySelector('select'), { target: { value: '12' } });
    expect(onUpdateDraft).toHaveBeenCalledWith('script-task', results[3].draft, { partId: 12 });
  });
});
