import request from './client';

export function getProjectParts(projectId) {
  return request(`/api/projects/${projectId}/parts/`);
}

export function getProjectPart(projectId, partId) {
  return request(`/api/projects/${projectId}/parts/${partId}`);
}

export function createProjectPart(projectId, payload) {
  return request(`/api/projects/${projectId}/parts/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProjectPart(projectId, partId, payload) {
  return request(`/api/projects/${projectId}/parts/${partId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProjectPart(projectId, partId) {
  return request(`/api/projects/${projectId}/parts/${partId}`, { method: 'DELETE' });
}

export function createPartCommit(partId, payload) {
  return request(`/api/parts/${partId}/commits`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getPartCommits(partId) {
  return request(`/api/parts/${partId}/commits`);
}

export function getPartCommit(partId, revisionId) {
  return request(`/api/parts/${partId}/commits/${revisionId}`);
}

export function restorePartCommit(partId, revisionId) {
  return request(`/api/parts/${partId}/commits/${revisionId}/restore`, {
    method: 'POST',
  });
}
