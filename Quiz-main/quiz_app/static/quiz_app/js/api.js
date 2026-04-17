const API_BASE = '/api/v1';

/** Хелпер: базовый fetch с авторизацией */
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Если токен истёк — пробуем обновить
  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`;
      return fetch(`${API_BASE}${path}`, { ...options, headers });
    } else {
      logout();
      return;
    }
  }

  return res;
}

/** Обновление access-токена через refresh */
async function tryRefreshToken() {
  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('access_token', data.access);
    return true;
  } catch {
    return false;
  }
}

/** Выход из системы */
function logout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/login.html';
}

/** Текущий пользователь из localStorage */
function getCurrentUser() {
  const raw = localStorage.getItem('user');
  try { return raw ? JSON.parse(raw) : null; } catch { return null; }
}

// ── Методы API ──────────────────────────────────────────────

const API = {
  /** Аутентификация */
  auth: {
    async login(email, password) {
      const res = await fetch(`${API_BASE}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      return res;
    },

    async register(data) {
      const res = await fetch(`${API_BASE}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return res;
    },

    async resetPassword(email) {
      return apiFetch('/auth/password-reset/', {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
    },
  },

  /** Профиль */
  profile: {
    async get()       { return apiFetch('/profile/'); },
    async update(data) {
      return apiFetch('/profile/', { method: 'PATCH', body: JSON.stringify(data) });
    },
    async changePassword(data) {
      return apiFetch('/profile/password/', { method: 'PUT', body: JSON.stringify(data) });
    },
  },

  /** Дашборд */
  async getDashboard() { return apiFetch('/dashboard/'); },

  /** Контент */
  subjects: {
    async list()       { return apiFetch('/subjects/'); },
    async get(id)      { return apiFetch(`/subjects/${id}/`); },
  },
  topics: {
    async list(subjectId) {
      const q = subjectId ? `?subject=${subjectId}` : '';
      return apiFetch(`/topics/${q}`);
    },
    async get(id)          { return apiFetch(`/topics/${id}/`); },
    async getProgress(id)  { return apiFetch(`/topics/${id}/progress/`); },
  },
  tasks: {
    async list(topicId) {
      const q = topicId ? `?topic=${topicId}` : '';
      return apiFetch(`/tasks/${q}`);
    },
    async get(id)     { return apiFetch(`/tasks/${id}/`); },
    async submit(id, data) {
      return apiFetch(`/tasks/${id}/submit/`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    async myAttempts(id) { return apiFetch(`/tasks/${id}/my_attempts/`); },
  },

  /** Прогресс */
  async getProgress() { return apiFetch('/progress/'); },

  /** Ачивки */
  async getAchievements()    { return apiFetch('/achievements/'); },
  async getMyAchievements()  { return apiFetch('/my-achievements/'); },

  /** Таблица лидеров */
  async getLeaderboard(classGroupId) {
    const q = classGroupId ? `?class_group=${classGroupId}` : '';
    return apiFetch(`/leaderboard/${q}`);
  },

  /** Классы (учитель) */
  classes: {
    async list()           { return apiFetch('/classes/'); },
    async get(id)          { return apiFetch(`/classes/${id}/`); },
    async leaderboard(id)  { return apiFetch(`/classes/${id}/leaderboard/`); },
    async addStudent(classId, studentId) {
      return apiFetch(`/classes/${classId}/add_student/`, {
        method: 'POST',
        body: JSON.stringify({ student_id: studentId }),
      });
    },
  },
};

export { API, logout, getCurrentUser };