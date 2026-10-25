import request from './client';

export function getProjectFindings(projectId) {
  return request(`/api/projects/${projectId}/findings`);
}

export function createProjectFinding(projectId, payload) {
  return request(`/api/projects/${projectId}/findings`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateFinding(findingId, payload) {
  return request(`/api/findings/${findingId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteFinding(findingId) {
  return request(`/api/findings/${findingId}`, { method: 'DELETE' });
}
