import request from './client';

export function sendProjectAiMessage(projectId, payload) {
  return request(`/api/projects/${projectId}/ai/message`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function executeProjectAiPlan(projectId, payload) {
  return request(`/api/projects/${projectId}/ai/execute`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
