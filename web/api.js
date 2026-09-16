// Every call the app makes. One place, so a shape change has one place to land.

async function send(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}

const asJson = (body) => ({
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  listCanvases: () => send('/api/canvases'),

  createCanvas: (markdown) =>
    send('/api/canvases', { method: 'POST', ...asJson({ markdown }) }),

  readCanvas: (id) => send(`/api/canvases/${id}`),

  patchCanvas: (id, patch) =>
    send(`/api/canvases/${id}`, { method: 'PATCH', ...asJson(patch) }),

  ask: (id, body) =>
    send(`/api/canvases/${id}/ask`, { method: 'POST', ...asJson(body) }),

  retry: (id, boxId) =>
    send(`/api/canvases/${id}/boxes/${boxId}/retry`, { method: 'POST' }),

  readBody: (id, boxId) => send(`/api/canvases/${id}/boxes/${boxId}/body`),

  writeBody: (id, boxId, markdown) =>
    send(`/api/canvases/${id}/boxes/${boxId}/body`, { method: 'PUT', ...asJson({ markdown }) }),

  deleteBox: (id, boxId) =>
    send(`/api/canvases/${id}/boxes/${boxId}`, { method: 'DELETE' }),

  streamUrl: (id, boxId) => `/api/canvases/${id}/boxes/${boxId}/stream`,
};
