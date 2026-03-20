export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  let token = null;
  if (typeof window !== 'undefined') {
    token = localStorage.getItem('omni_admin_token');
  }

  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  headers.set('Content-Type', 'application/json');

  const config: RequestInit = {
    ...options,
    headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (!response.ok) {
    if (response.status === 401 && endpoint.startsWith('/admin') && typeof window !== 'undefined') {
      localStorage.removeItem('omni_admin_token');
      window.location.href = '/login';
    }
    const errorDetails = await response.text();
    throw new Error(`Erro na API ${response.status}: ${errorDetails}`);
  }

  return response.json();
}
