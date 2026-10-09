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

  createCanvas: (markdown, webSearch) =>
    send('/api/canvases', { method: 'POST', ...asJson({ markdown, webSearch }) }),

  // A stream, so the brief is read as it is written. The address, not the call.
  expandUrl: (topic) => `/api/research/expand?topic=${encodeURIComponent(topic)}`,

  startResearch: (topic, prompt) =>
    send('/api/research', { method: 'POST', ...asJson({ topic, prompt }) }),

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

  // Raw bytes, not a form: the content type is the file's own, and the server checks it.
  uploadAsset: (id, file) =>
    send(`/api/canvases/${id}/assets`, {
      method: 'POST',
      headers: { 'content-type': file.type || 'application/octet-stream' },
      body: file,
    }),

  streamUrl: (id, boxId) => `/api/canvases/${id}/boxes/${boxId}/stream`,

  // Folding an answer into its parent. Keyed by the answer, because the answer is what
  // is being folded in; the review renders in the parent, which is where it lands.
  openMerge: (id, boxId, guidance) =>
    send(`/api/canvases/${id}/boxes/${boxId}/merge`, { method: 'POST', ...asJson({ guidance }) }),

  readMerge: (id, boxId) => send(`/api/canvases/${id}/boxes/${boxId}/merge`),

  patchMerge: (id, boxId, patch) =>
    send(`/api/canvases/${id}/boxes/${boxId}/merge`, { method: 'PATCH', ...asJson(patch) }),

  // `removeChild` says which button was pressed: accept, or accept and take the answer
  // off the canvas. One request either way, so the two never come apart.
  acceptMerge: (id, boxId, removeChild = false) =>
    send(`/api/canvases/${id}/boxes/${boxId}/merge/accept`, {
      method: 'POST',
      ...asJson({ removeChild }),
    }),

  rejectMerge: (id, boxId) =>
    send(`/api/canvases/${id}/boxes/${boxId}/merge`, { method: 'DELETE' }),

  mergeStreamUrl: (id, boxId) => `/api/canvases/${id}/boxes/${boxId}/merge/stream`,

  // Global, not per canvas: the same instructions ride on every run.
  readInstructions: () => send('/api/instructions'),

  writeInstructions: (markdown) =>
    send('/api/instructions', { method: 'PUT', ...asJson({ markdown }) }),

  // Global as well: the chips the ask popover offers, whatever canvas is open.
  readPresets: () => send('/api/presets'),

  writePresets: (presets) =>
    send('/api/presets', { method: 'PUT', ...asJson({ presets }) }),
};
