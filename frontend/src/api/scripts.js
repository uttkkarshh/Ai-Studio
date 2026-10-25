import request from './client';

export function getPartScript(partId) {
  return request(`/api/parts/${partId}/script`, { notFoundAsNull: true });
}

export function getScriptRevisions(scriptId) {
  return request(`/api/scripts/${scriptId}/revisions`);
}

export function getPartScriptDrafts(partId) {
  return request(`/api/parts/${partId}/script-drafts`);
}

export function createScriptDraft(partId, payload) {
  return request(`/api/parts/${partId}/script-drafts`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getScriptDraft(draftId) {
  return request(`/api/script-drafts/${draftId}`);
}

export function updateScriptDraft(draftId, payload) {
  return request(`/api/script-drafts/${draftId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function getScriptRevision(scriptId, revisionId) {
  return request(`/api/scripts/${scriptId}/revisions/${revisionId}`);
}

export function acceptScriptDraft(draftId) {
  return request(`/api/script-drafts/${draftId}/accept`, {
    method: 'POST',
  });
}

export function restoreScriptRevision(scriptId, revisionId) {
  return request(`/api/scripts/${scriptId}/revisions/${revisionId}/restore`, {
    method: 'POST',
  });
}
