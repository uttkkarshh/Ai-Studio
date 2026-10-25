const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const { notFoundAsNull = false, ...fetchOptions } = options;
  const method = fetchOptions.method || 'GET';
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(fetchOptions.headers || {}),
      },
      ...fetchOptions,
    });
  } catch (networkError) {
    throw new Error(`Network request failed for ${method} ${path}: ${networkError.message || 'connection unavailable'}`, { cause: networkError });
  }

  if (response.status === 204) {
    return null;
  }

  if (response.status === 404 && notFoundAsNull) {
    return null;
  }

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload ? payload.detail : payload;
    const detailMessage = typeof detail === 'string'
      ? detail
      : detail
        ? JSON.stringify(detail)
        : 'Request failed';
    const message = `HTTP ${response.status}: ${detailMessage}`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export default request;
