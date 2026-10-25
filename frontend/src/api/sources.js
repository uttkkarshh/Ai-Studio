import request from './client';

export function getProjectSources(projectId) {
  return request(`/api/projects/${projectId}/sources/`);
}

export function createProjectSource(projectId, payload) {
  return request(`/api/projects/${projectId}/sources/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProjectSource(projectId, sourceId, payload) {
  return request(`/api/projects/${projectId}/sources/${sourceId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProjectSource(projectId, sourceId) {
  return request(`/api/projects/${projectId}/sources/${sourceId}`, { method: 'DELETE' });
}
