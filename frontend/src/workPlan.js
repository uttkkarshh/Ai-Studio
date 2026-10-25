const allowedActions = new Set([
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
]);

const allowedTargetTypes = new Set([
  'project',
  'part',
  'source',
  'finding',
  'asset',
  'script_draft',
  'script',
  'part_relationship',
]);

export function normalizeWorkPlanProposal(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  if (value.type && value.type !== 'work_plan') return null;

  const plan = value.type === 'work_plan' ? value.data : value;
  if (!plan || typeof plan !== 'object' || Array.isArray(plan)) return null;
  if (typeof plan.objective !== 'string' || !plan.objective.trim()) return null;
  if (typeof plan.rationale !== 'string' || !Array.isArray(plan.tasks)) return null;
  if (plan.tasks.length < 1 || plan.tasks.length > 5) return null;

  const taskIds = new Set();
  const tasks = [];
  for (const task of plan.tasks) {
    if (!task || typeof task !== 'object' || Array.isArray(task)) return null;
    if (typeof task.task_id !== 'string' || !task.task_id.trim() || taskIds.has(task.task_id.trim())) return null;
    if (typeof task.title !== 'string' || !task.title.trim()) return null;
    if (!allowedActions.has(task.action) || typeof task.capability !== 'string' || !task.capability.trim()) return null;
    if (!allowedTargetTypes.has(task.target_type)) return null;
    if (task.target_id != null && (!Number.isInteger(task.target_id) || task.target_id < 1)) return null;
    if (typeof task.intent !== 'string' || typeof task.expected_output !== 'string') return null;
    if (!Array.isArray(task.completion_criteria) || task.completion_criteria.length === 0) return null;
    if (task.completion_criteria.some((criterion) => typeof criterion !== 'string' || !criterion.trim())) return null;

    taskIds.add(task.task_id.trim());
    tasks.push({
      task_id: task.task_id.trim(),
      title: task.title.trim(),
      action: task.action,
      capability: task.capability.trim(),
      target_type: task.target_type,
      target_id: task.target_id ?? null,
      intent: task.intent.trim(),
      expected_output: task.expected_output.trim(),
      completion_criteria: task.completion_criteria.map((criterion) => criterion.trim()),
    });
  }

  return {
    type: 'work_plan',
    objective: plan.objective.trim(),
    rationale: plan.rationale.trim(),
    tasks,
  };
}

export function parseAiResponse(response) {
  const proposal = response && typeof response === 'object' ? response.proposal : null;
  const message = getAiResponseMessage(response);

  if (proposal == null) {
    return { type: 'message', message };
  }

  if (proposal.type === 'work_plan') {
    const workPlan = normalizeWorkPlanProposal(proposal);
    return workPlan
      ? { type: 'work_plan', workPlan, message }
      : { type: 'fallback', message: 'The AI returned a malformed work plan. No changes were applied.' };
  }

  if (proposal.type === 'project_plan') {
    return { type: 'fallback', message: 'This legacy project plan is not supported here. No Parts were created.' };
  }

  return { type: 'fallback', message: 'The AI returned an unsupported proposal. No changes were applied.' };
}

export function getAiResponseMessage(response) {
  if (typeof response === 'string' && response.trim()) return response.trim();
  if (response && typeof response === 'object') {
    if (typeof response.message === 'string' && response.message.trim()) return response.message.trim();
    if (typeof response.action?.reason === 'string' && response.action.reason.trim()) return response.action.reason.trim();
  }
  return 'The AI did not return a message.';
}

export function toWorkPlanProposalPayload(workPlan) {
  return {
    type: 'work_plan',
    data: {
      objective: workPlan.objective,
      rationale: workPlan.rationale,
      tasks: workPlan.tasks.map((task) => ({
        task_id: task.task_id,
        title: task.title,
        action: task.action,
        capability: task.capability,
        target_type: task.target_type,
        target_id: task.target_id ?? null,
        intent: task.intent,
        expected_output: task.expected_output,
        completion_criteria: [...task.completion_criteria],
      })),
    },
  };
}

export function updateWorkPlanTask(plan, taskId, updatedTask) {
  return {
    ...plan,
    tasks: plan.tasks.map((task) => (task.task_id === taskId ? { ...task, ...updatedTask, task_id: taskId } : task)),
  };
}

export function removeWorkPlanTask(plan, taskId) {
  return { ...plan, tasks: plan.tasks.filter((task) => task.task_id !== taskId) };
}

export function addWorkPlanTask(plan, task) {
  if (plan.tasks.length >= 5) throw new Error('A WorkPlan can contain no more than five tasks.');
  if (plan.tasks.some((existingTask) => existingTask.task_id === task.task_id)) {
    throw new Error('Task IDs must be unique within a WorkPlan.');
  }
  return { ...plan, tasks: [...plan.tasks, task] };
}
