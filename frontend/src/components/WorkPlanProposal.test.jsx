// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import WorkPlanProposal from './WorkPlanProposal';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const initialPlan = {
  type: 'work_plan',
  objective: 'Review coastal resilience',
  rationale: 'Organize evidence before drafting.',
  tasks: [
    {
      task_id: 'research-risk',
      title: 'Research coastal flood risk',
      action: 'research',
      capability: 'research',
      target_type: 'project',
      target_id: 12,
      intent: 'Gather evidence on coastal flood risks.',
      expected_output: 'Relevant evidence and source candidates.',
      completion_criteria: ['Evidence addresses the project objective.', 'Sources are recorded.'],
    },
  ],
};

function renderProposal({ onAccept = vi.fn(), onRequestChanges = vi.fn().mockResolvedValue(true) } = {}) {
  function Harness() {
    const [plan, setPlan] = useState(initialPlan);
    const [status, setStatus] = useState('awaiting_approval');
    const [validationPending, setValidationPending] = useState(false);
    return (
      <WorkPlanProposal
        plan={plan}
        status={status}
        validationPending={validationPending}
        onPlanChange={(updatedPlan, needsValidation) => {
          setPlan(updatedPlan);
          setValidationPending(needsValidation);
          setStatus('revised');
        }}
        onAccept={() => {
          onAccept();
        }}
        onDismiss={vi.fn()}
        onRequestChanges={onRequestChanges}
      />
    );
  }

  return render(<Harness />);
}

describe('WorkPlanProposal', () => {
  it('renders the summary and task details as a card, including criteria', () => {
    renderProposal();

    expect(screen.getByText('Review coastal resilience')).toBeTruthy();
    expect(screen.getByText('Organize evidence before drafting.')).toBeTruthy();
    expect(screen.getByText('1', { selector: '.work-plan-summary p' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Research coastal flood risk' })).toBeTruthy();
    expect(screen.getByText('research-risk')).toBeTruthy();
    expect(screen.getByText('Evidence addresses the project objective.')).toBeTruthy();
    expect(screen.getByText('Sources are recorded.')).toBeTruthy();
    expect(document.querySelectorAll('.proposal-task-card')).toHaveLength(1);
    expect(document.querySelector('.proposal-task-card').textContent).toContain('Capability: research');
  });

  it('supports local task editing and removal', () => {
    renderProposal();

    fireEvent.click(screen.getByRole('button', { name: 'Edit task' }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Assess coastal flood risk' } });
    fireEvent.change(screen.getByLabelText('Intent'), { target: { value: 'Compare regional risk indicators.' } });
    fireEvent.change(screen.getByLabelText('Expected output'), { target: { value: 'A regional risk comparison.' } });
    fireEvent.change(screen.getByLabelText('Completion criteria'), { target: { value: 'Regional indicators are compared.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save task' }));

    expect(screen.getByRole('heading', { name: 'Assess coastal flood risk' })).toBeTruthy();
    expect(screen.getByText('Regional indicators are compared.')).toBeTruthy();
    expect(screen.getByText(/Local edits have not been validated/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Remove task' }));
    expect(screen.getByText('No tasks in this WorkPlan.')).toBeTruthy();
  });

  it('allows adding a local task and marks it for backend validation', () => {
    renderProposal();

    fireEvent.click(screen.getByRole('button', { name: 'Add task' }));
    fireEvent.change(screen.getByLabelText('Task ID'), { target: { value: 'create-part' } });
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Create a flood-risk Part' } });
    fireEvent.change(screen.getByLabelText('Action'), { target: { value: 'create' } });
    fireEvent.change(screen.getByLabelText('Capability'), { target: { value: 'create_part' } });
    fireEvent.change(screen.getByLabelText('Target type'), { target: { value: 'part' } });
    fireEvent.change(screen.getByLabelText('Intent'), { target: { value: 'Organize flood risk research.' } });
    fireEvent.change(screen.getByLabelText('Expected output'), { target: { value: 'A focused project Part.' } });
    fireEvent.change(screen.getByLabelText('Completion criteria'), { target: { value: 'The Part has a clear objective.' } });
    fireEvent.click(screen.getAllByRole('button', { name: 'Add task' }).at(-1));

    expect(screen.getByRole('heading', { name: 'Create a flood-risk Part' })).toBeTruthy();
    expect(screen.getByText(/Approval submits this final plan for validation/)).toBeTruthy();
  });

  it('requests execution without claiming success before backend confirmation', () => {
    const onAccept = vi.fn();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderProposal({ onAccept });

    fireEvent.click(screen.getByRole('button', { name: 'Approve & execute plan' }));

    expect(onAccept).toHaveBeenCalledOnce();
    expect(screen.queryByText(/backend confirmed execution/i)).toBeNull();
    expect(screen.queryByText(/saved and accepted/i)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows completion only when the parent confirms backend execution', () => {
    render(
      <WorkPlanProposal
        plan={initialPlan}
        status="approved"
        validationPending={false}
        executionConfirmed
        onPlanChange={vi.fn()}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onRequestChanges={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Execution response received' }).disabled).toBe(true);
    expect(screen.getByText(/The backend processed the approved plan/)).toBeTruthy();
  });

  it('dismisses the proposal locally', () => {
    const onDismiss = vi.fn();
    render(
      <WorkPlanProposal
        plan={initialPlan}
        status="awaiting_approval"
        validationPending={false}
        onPlanChange={vi.fn()}
        onAccept={vi.fn()}
        onDismiss={onDismiss}
        onRequestChanges={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));

    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('preserves the current proposal when a revision response is invalid', async () => {
    const onRequestChanges = vi.fn().mockResolvedValue(false);
    renderProposal({ onRequestChanges });
    fireEvent.change(screen.getByLabelText('Request AI changes'), {
      target: { value: 'Add a local adaptation task.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Request changes' }));

    await waitFor(() => expect(onRequestChanges).toHaveBeenCalledWith('Add a local adaptation task.'));
    expect(screen.getByRole('heading', { name: 'Research coastal flood risk' })).toBeTruthy();
    expect(screen.getByLabelText('Request AI changes').value).toBe('Add a local adaptation task.');
  });
});
