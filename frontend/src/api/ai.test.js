import { describe, expect, it, vi } from 'vitest';
import request from './client';
import { executeProjectAiPlan } from './ai';

vi.mock('./client', () => ({ default: vi.fn() }));

describe('executeProjectAiPlan', () => {
  it('uses the existing project execution route and serializes the backend request shape', async () => {
    request.mockResolvedValue({ project_id: 9, status: 'drafts_ready', objective: 'Create a Part', tasks: [] });
    const payload = {
      plan: {
        objective: 'Create a Part',
        rationale: 'Organize the work.',
        tasks: [],
      },
      scope: 'project',
      part_id: null,
      user_request: 'Create a Part',
    };

    const response = await executeProjectAiPlan(9, payload);

    expect(request).toHaveBeenCalledWith('/api/projects/9/ai/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    expect(response.status).toBe('drafts_ready');
  });
});
