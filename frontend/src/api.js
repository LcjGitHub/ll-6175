import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

/**
 * @typedef {Object} Game
 * @property {number} id
 * @property {string} name
 * @property {number} [part_count]
 */

/**
 * @typedef {Object} MissingPart
 * @property {number} id
 * @property {number} game_id
 * @property {string} accessory
 * @property {string} replacement_plan
 * @property {number} cost
 * @property {string|null} completion_date
 */

export const gameApi = {
  /** @returns {Promise<Game[]>} */
  list: () => api.get('/games').then((r) => r.data),

  /** @param {{ name: string }} data */
  create: (data) => api.post('/games', data).then((r) => r.data),

  /** @param {number} id @param {{ name: string }} data */
  update: (id, data) => api.put(`/games/${id}`, data).then((r) => r.data),

  /** @param {number} id */
  remove: (id) => api.delete(`/games/${id}`),
}

export const partApi = {
  /** @param {number} gameId @returns {Promise<MissingPart[]>} */
  list: (gameId) => api.get(`/games/${gameId}/parts`).then((r) => r.data),

  /** @param {number} gameId @param {Omit<MissingPart, 'id'|'game_id'>} data */
  create: (gameId, data) =>
    api.post(`/games/${gameId}/parts`, data).then((r) => r.data),

  /** @param {number} id @param {Omit<MissingPart, 'id'|'game_id'>} data */
  update: (id, data) => api.put(`/parts/${id}`, data).then((r) => r.data),

  /** @param {number} id */
  remove: (id) => api.delete(`/parts/${id}`),
}

/**
 * @typedef {Object} GameRankItem
 * @property {number} id
 * @property {string} name
 * @property {number} part_count
 * @property {number} total_cost
 */

/**
 * @typedef {Object} StatsSummary
 * @property {number} total_parts
 * @property {number} completed_parts
 * @property {number} pending_parts
 * @property {number} total_cost
 * @property {GameRankItem[]} game_ranking
 */

export const statsApi = {
  /** @returns {Promise<StatsSummary>} */
  summary: () => api.get('/stats/summary').then((r) => r.data),
}

export default api
