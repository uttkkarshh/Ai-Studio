import request from './client';

export function getProjects() {
  return request('/api/projects/');
}

export function getProject(projectId) {
  return request(`/api/projects/${projectId}`);
}

export function createProject(payload) {
  return request('/api/projects/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProject(projectId, payload) {
  return request(`/api/projects/${projectId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProject(projectId) {
  return request(`/api/projects/${projectId}`, { method: 'DELETE' });
}
