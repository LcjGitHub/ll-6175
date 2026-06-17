<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DatePicker from 'primevue/datepicker'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Tag from 'primevue/tag'

import { gameApi, partApi } from './api'

const toast = useToast()
const confirm = useConfirm()

const games = ref([])
const selectedGame = ref(null)
const parts = ref([])
const loadingGames = ref(false)
const loadingParts = ref(false)

const gameDialog = ref(false)
const gameForm = ref({ id: null, name: '' })

const partDialog = ref(false)
const partForm = ref({
  id: null,
  accessory: '',
  replacement_plan: '',
  cost: 0,
  completion_date: null,
})

/** @param {unknown} err */
function showError(err, fallback = '操作失败') {
  const msg = err?.response?.data?.error || fallback
  toast.add({ severity: 'error', summary: '错误', detail: msg, life: 3000 })
}

async function loadGames() {
  loadingGames.value = true
  try {
    games.value = await gameApi.list()
    if (selectedGame.value) {
      const found = games.value.find((g) => g.id === selectedGame.value.id)
      selectedGame.value = found ?? null
    }
  } catch (err) {
    showError(err, '加载游戏列表失败')
  } finally {
    loadingGames.value = false
  }
}

async function loadParts() {
  if (!selectedGame.value) {
    parts.value = []
    return
  }
  loadingParts.value = true
  try {
    parts.value = await partApi.list(selectedGame.value.id)
  } catch (err) {
    showError(err, '加载缺件列表失败')
  } finally {
    loadingParts.value = false
  }
}

function selectGame(game) {
  selectedGame.value = game
  loadParts()
}

function openGameDialog(game = null) {
  gameForm.value = game
    ? { id: game.id, name: game.name }
    : { id: null, name: '' }
  gameDialog.value = true
}

async function saveGame() {
  const name = gameForm.value.name.trim()
  if (!name) {
    toast.add({ severity: 'warn', summary: '提示', detail: '请输入游戏名称', life: 3000 })
    return
  }
  try {
    if (gameForm.value.id) {
      await gameApi.update(gameForm.value.id, { name })
      toast.add({ severity: 'success', summary: '成功', detail: '游戏已更新', life: 2000 })
    } else {
      await gameApi.create({ name })
      toast.add({ severity: 'success', summary: '成功', detail: '游戏已添加', life: 2000 })
    }
    gameDialog.value = false
    await loadGames()
  } catch (err) {
    showError(err)
  }
}

function confirmDeleteGame(game) {
  confirm.require({
    message: `确定删除「${game.name}」及其全部缺件记录？`,
    header: '确认删除',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await gameApi.remove(game.id)
        if (selectedGame.value?.id === game.id) {
          selectedGame.value = null
          parts.value = []
        }
        toast.add({ severity: 'success', summary: '成功', detail: '游戏已删除', life: 2000 })
        await loadGames()
      } catch (err) {
        showError(err)
      }
    },
  })
}

function openPartDialog(part = null) {
  partForm.value = part
    ? {
        id: part.id,
        accessory: part.accessory,
        replacement_plan: part.replacement_plan,
        cost: part.cost,
        completion_date: part.completion_date ? new Date(part.completion_date) : null,
      }
    : {
        id: null,
        accessory: '',
        replacement_plan: '',
        cost: 0,
        completion_date: null,
      }
  partDialog.value = true
}

/** @param {Date|null} date */
function formatDate(date) {
  if (!date) return null
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

async function savePart() {
  if (!selectedGame.value) return

  const payload = {
    accessory: partForm.value.accessory.trim(),
    replacement_plan: partForm.value.replacement_plan.trim(),
    cost: partForm.value.cost ?? 0,
    completion_date: formatDate(partForm.value.completion_date),
  }

  if (!payload.accessory || !payload.replacement_plan) {
    toast.add({ severity: 'warn', summary: '提示', detail: '请填写配件和替换方案', life: 3000 })
    return
  }

  try {
    if (partForm.value.id) {
      await partApi.update(partForm.value.id, payload)
      toast.add({ severity: 'success', summary: '成功', detail: '缺件已更新', life: 2000 })
    } else {
      await partApi.create(selectedGame.value.id, payload)
      toast.add({ severity: 'success', summary: '成功', detail: '缺件已添加', life: 2000 })
    }
    partDialog.value = false
    await loadParts()
    await loadGames()
  } catch (err) {
    showError(err)
  }
}

function confirmDeletePart(part) {
  confirm.require({
    message: `确定删除缺件「${part.accessory}」？`,
    header: '确认删除',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await partApi.remove(part.id)
        toast.add({ severity: 'success', summary: '成功', detail: '缺件已删除', life: 2000 })
        await loadParts()
        await loadGames()
      } catch (err) {
        showError(err)
      }
    },
  })
}

onMounted(loadGames)
</script>

<template>
  <Toast />
  <ConfirmDialog />

  <div class="app-shell">
    <header class="app-header">
      <div>
        <h1>桌游缺件替换记录</h1>
        <p class="subtitle">管理桌游配件缺失与替换方案</p>
      </div>
    </header>

    <div class="layout">
      <!-- 游戏列表 -->
      <aside class="panel game-panel">
        <div class="panel-header">
          <h2>桌游列表</h2>
          <Button icon="pi pi-plus" label="新增" size="small" @click="openGameDialog()" />
        </div>

        <div v-if="loadingGames" class="empty-hint">加载中…</div>
        <ul v-else-if="games.length" class="game-list">
          <li
            v-for="game in games"
            :key="game.id"
            :class="['game-item', { active: selectedGame?.id === game.id }]"
            @click="selectGame(game)"
          >
            <div class="game-info">
              <span class="game-name">{{ game.name }}</span>
              <Tag :value="`${game.part_count ?? 0} 条缺件`" severity="secondary" />
            </div>
            <div class="game-actions" @click.stop>
              <Button
                icon="pi pi-pencil"
                text
                rounded
                size="small"
                @click="openGameDialog(game)"
              />
              <Button
                icon="pi pi-trash"
                text
                rounded
                severity="danger"
                size="small"
                @click="confirmDeleteGame(game)"
              />
            </div>
          </li>
        </ul>
        <div v-else class="empty-hint">暂无游戏，点击「新增」添加</div>
      </aside>

      <!-- 缺件详情 -->
      <main class="panel parts-panel">
        <div class="panel-header">
          <h2>
            {{ selectedGame ? `「${selectedGame.name}」缺件详情` : '缺件详情' }}
          </h2>
          <Button
            v-if="selectedGame"
            icon="pi pi-plus"
            label="新增缺件"
            size="small"
            @click="openPartDialog()"
          />
        </div>

        <div v-if="!selectedGame" class="empty-hint large">
          <i class="pi pi-arrow-left" />
          请从左侧选择一个桌游
        </div>

        <DataTable
          v-else
          :value="parts"
          :loading="loadingParts"
          striped-rows
          paginator
          :rows="10"
          data-key="id"
          class="parts-table"
        >
          <Column field="accessory" header="配件" sortable />
          <Column field="replacement_plan" header="替换方案" />
          <Column field="cost" header="成本 (¥)" sortable>
            <template #body="{ data }">
              {{ Number(data.cost).toFixed(2) }}
            </template>
          </Column>
          <Column field="completion_date" header="完成日期" sortable>
            <template #body="{ data }">
              <Tag
                v-if="data.completion_date"
                :value="data.completion_date"
                severity="success"
              />
              <Tag v-else value="未完成" severity="warn" />
            </template>
          </Column>
          <Column header="操作" style="width: 8rem">
            <template #body="{ data }">
              <Button
                icon="pi pi-pencil"
                text
                rounded
                size="small"
                @click="openPartDialog(data)"
              />
              <Button
                icon="pi pi-trash"
                text
                rounded
                severity="danger"
                size="small"
                @click="confirmDeletePart(data)"
              />
            </template>
          </Column>
        </DataTable>
      </main>
    </div>

    <!-- 游戏对话框 -->
    <Dialog
      v-model:visible="gameDialog"
      :header="gameForm.id ? '编辑游戏' : '新增游戏'"
      modal
      :style="{ width: '24rem' }"
    >
      <div class="form-field">
        <label for="game-name">游戏名称</label>
        <InputText id="game-name" v-model="gameForm.name" autofocus class="w-full" />
      </div>
      <template #footer>
        <Button label="取消" text @click="gameDialog = false" />
        <Button label="保存" @click="saveGame" />
      </template>
    </Dialog>

    <!-- 缺件对话框 -->
    <Dialog
      v-model:visible="partDialog"
      :header="partForm.id ? '编辑缺件' : '新增缺件'"
      modal
      :style="{ width: '28rem' }"
    >
      <div class="form-stack">
        <div class="form-field">
          <label for="part-accessory">配件</label>
          <InputText id="part-accessory" v-model="partForm.accessory" class="w-full" />
        </div>
        <div class="form-field">
          <label for="part-plan">替换方案</label>
          <InputText id="part-plan" v-model="partForm.replacement_plan" class="w-full" />
        </div>
        <div class="form-field">
          <label for="part-cost">成本 (¥)</label>
          <InputNumber
            id="part-cost"
            v-model="partForm.cost"
            mode="currency"
            currency="CNY"
            locale="zh-CN"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label for="part-date">完成日期</label>
          <DatePicker
            id="part-date"
            v-model="partForm.completion_date"
            date-format="yy-mm-dd"
            show-icon
            show-button-bar
            placeholder="未完成可留空"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <Button label="取消" text @click="partDialog = false" />
        <Button label="保存" @click="savePart" />
      </template>
    </Dialog>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
}

.w-full {
  width: 100%;
}
</style>

<style scoped>
.app-shell {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
}

.app-header {
  margin-bottom: 1.5rem;
}

.app-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
}

.subtitle {
  margin: 0.25rem 0 0;
  color: #64748b;
  font-size: 0.95rem;
}

.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 768px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.panel {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 1rem;
  min-height: 420px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.game-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.game-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}

.game-item:hover {
  background: #f8fafc;
}

.game-item.active {
  background: #eff6ff;
  border-color: #93c5fd;
}

.game-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.game-name {
  font-weight: 500;
}

.game-actions {
  display: flex;
  gap: 0.15rem;
}

.empty-hint {
  color: #94a3b8;
  text-align: center;
  padding: 2rem 1rem;
  font-size: 0.9rem;
}

.empty-hint.large {
  padding: 4rem 1rem;
  font-size: 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.empty-hint.large .pi {
  font-size: 1.5rem;
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-field label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #475569;
}

.parts-table {
  font-size: 0.9rem;
}
</style>
