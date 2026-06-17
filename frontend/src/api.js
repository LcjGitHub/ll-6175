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
 * @typedef {Object} PurchaseChannel
 * @property {number} id
 * @property {string} name
 * @property {string|null} contact
 * @property {string|null} remark
 * @property {number} [part_count]
 */

/**
 * @typedef {Object} MissingPart
 * @property {number} id
 * @property {number} game_id
 * @property {number|null} channel_id
 * @property {string|null} channel_name
 * @property {string} accessory
 * @property {string} replacement_plan
 * @property {number} cost
 * @property {string|null} completion_date
 * @property {'高'|'中'|'低'} priority
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

export const channelApi = {
  /** @returns {Promise<PurchaseChannel[]>} */
  list: () => api.get('/channels').then((r) => r.data),

  /** @param {{ name: string, contact?: string, remark?: string }} data */
  create: (data) => api.post('/channels', data).then((r) => r.data),

  /** @param {number} id @param {{ name: string, contact?: string, remark?: string }} data */
  update: (id, data) => api.put(`/channels/${id}`, data).then((r) => r.data),

  /** @param {number} id */
  remove: (id) => api.delete(`/channels/${id}`),
}

export const partApi = {
  /** @param {number} gameId @param {string} [priority] @returns {Promise<MissingPart[]>} */
  list: (gameId, priority) => {
    const params = {}
    if (priority) params.priority = priority
    return api.get(`/games/${gameId}/parts`, { params }).then((r) => r.data)
  },

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

/**
 * @typedef {Object} OperationLog
 * @property {number} id
 * @property {string} op_type
 * @property {string} target
 * @property {string|null} detail
 * @property {string} created_at
 */

export const logApi = {
  /** @param {string} [opType] @returns {Promise<OperationLog[]>} */
  list: (opType) => {
    const params = opType ? { op_type: opType } : {}
    return api.get('/logs', { params }).then((r) => r.data)
  },
}

/**
 * @typedef {Object} ImportSummary
 * @property {number} games_inserted
 * @property {number} channels_inserted
 * @property {number} parts_inserted
 * @property {number} parts_skipped
 */

/**
 * @typedef {Object} ImportResult
 * @property {string} message
 * @property {'overwrite'|'merge'} mode
 * @property {ImportSummary} summary
 */

export const backupApi = {
  /** 触发浏览器下载备份 JSON 文件 */
  export: async () => {
    const resp = await api.get('/backup/export', { responseType: 'blob' })
    const blob = resp.data
    const disposition = resp.headers['content-disposition'] || ''
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    const filename = match ? match[1].replace(/['"]/g, '') : 'boardgame_backup.json'
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  },

  /**
   * 上传并导入备份文件
   * @param {File} file
   * @param {'overwrite'|'merge'} mode
   * @returns {Promise<ImportResult>}
   */
  import: (file, mode = 'merge') => {
    const formData = new FormData()
    formData.append('file', file)
    return api
      .post(`/backup/import?mode=${mode}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
}

export default api
