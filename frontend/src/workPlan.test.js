import { describe, expect, it } from 'vitest';
import {
  addWorkPlanTask,
  getAiResponseMessage,
  normalizeWorkPlanProposal,
  parseAiResponse,
  removeWorkPlanTask,
  toWorkPlanProposalPayload,
  updateWorkPlanTask,
} from './workPlan';

const plan = {
  type: 'work_plan',
  objective: 'Review coastal resilience',
  rationale: 'The objective needs organized research.',
  tasks: [
    {
      task_id: 'research-risk',
      title: 'Research coastal flood risk',
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

describe('WorkPlan response handling', () => {
  it('extracts a valid work_plan proposal from the API envelope', () => {
    expect(normalizeWorkPlanProposal({ type: 'work_plan', data: plan })).toMatchObject({
      type: 'work_plan',
      objective: plan.objective,
      tasks: [{ task_id: 'research-risk', completion_criteria: plan.tasks[0].completion_criteria }],
    });
  });

  it('keeps conversational responses as messages rather than empty plans', () => {
    const response = { action: { action: 'answer' }, message: 'The project studies coastal resilience.' };
    expect(parseAiResponse(response)).toEqual({
      type: 'message',
      message: 'The project studies coastal resilience.',
    });
    expect(normalizeWorkPlanProposal(response)).toBeNull();
  });

  it('handles malformed, legacy, and unknown proposals with safe fallbacks', () => {
    expect(parseAiResponse({ proposal: { type: 'work_plan', data: { objective: 'Missing tasks' } } }).type).toBe('fallback');
    expect(parseAiResponse({ proposal: { type: 'project_plan', data: { parts: [] } } }).message).toContain('legacy project plan');
    expect(parseAiResponse({ proposal: { type: 'future_plan', data: {} } }).type).toBe('fallback');
    expect(getAiResponseMessage({})).toBe('The AI did not return a message.');
  });

  it('serializes only the WorkPlan proposal contract for revisions', () => {
    expect(toWorkPlanProposalPayload(plan)).toEqual({
      type: 'work_plan',
      data: {
        objective: plan.objective,
        rationale: plan.rationale,
        tasks: plan.tasks,
      },
    });
  });
});

describe('local WorkPlan draft operations', () => {
  it('edits and removes tasks locally', () => {
    const edited = updateWorkPlanTask(plan, 'research-risk', { title: 'Assess flood risk' });
    expect(edited.tasks[0].title).toBe('Assess flood risk');
    expect(removeWorkPlanTask(edited, 'research-risk').tasks).toEqual([]);
    expect(plan.tasks[0].title).toBe('Research coastal flood risk');
  });

  it('adds tasks but preserves the five-task limit and unique IDs', () => {
    const task = { ...plan.tasks[0], task_id: 'create-part', capability: 'create_part', action: 'create', target_type: 'part' };
    expect(addWorkPlanTask(plan, task).tasks).toHaveLength(2);
    expect(() => addWorkPlanTask(plan, plan.tasks[0])).toThrow('unique');

    const fullPlan = { ...plan, tasks: Array.from({ length: 5 }, (_, index) => ({ ...plan.tasks[0], task_id: `task-${index}` })) };
    expect(() => addWorkPlanTask(fullPlan, task)).toThrow('no more than five');
  });
});
