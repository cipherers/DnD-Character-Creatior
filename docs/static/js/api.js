/**
 * Centralized API fetch utility.
 * Handles credentials, base URL, and error checking.
 */

async function apiFetch(endpoint, options = {}) {
    options.credentials = 'include';

    // Add Token Auth for mobile/ITP support
    const token = localStorage.getItem('dnd_auth_token');
    if (token) {
        options.headers = options.headers || {};
        options.headers['X-Auth-Token'] = token;
    }

    // Ensure absolute URL if not already
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

    try {
        const response = await fetch(url, options);

        if (response.status === 401) {
            // Unauthorized - usually session expired
            if (!window.location.pathname.endsWith('login.html')) {
                window.location.href = 'login.html';
            }
            return null;
        }

        if (!response.ok) {
            // Attempt to read as JSON first for structured errors
            let errorDetail = 'Unknown error';
            const contentType = response.headers.get('content-type');

            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                errorDetail = data.error || data.message || errorDetail;
            } else {
                // Fallback to text if not JSON (e.g. 404 HTML page)
                const text = await response.text();
                errorDetail = `Server Error (${response.status}): ${text.substring(0, 100)}...`;
                console.error('Non-JSON error response:', text);
            }

            // Log for debugging but return a structured object for the UI
            return { error: errorDetail, status: response.status, ok: false };
        }

        // If OK, parse as JSON
        return await response.json();

    } catch (error) {
        console.error('Network or Parsing Error:', error);
        return { error: 'Network error or invalid response from server', ok: false };
    }
}

// Make it globally available
window.apiFetch = apiFetch;
