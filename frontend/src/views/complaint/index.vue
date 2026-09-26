<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>公众诉求管理</h2>
        <p class="page-desc">维护诉求记录，围绕诉求编号、诉求来源、诉求内容、涉及设施做登记、筛选与状态流转。受理、回复与统计共用同一份办理期限与超期判定。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记诉求记录</button>
        <button class="btn" type="button" @click="exportRows">导出公众诉求清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="{ 'stat-warn': item.label === '超期件数' }">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>超期判定</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span class="overdue-tag" :class="overdueClass(row)">
              {{ row['是否超期'] ? '已超期' : (row['办理期限'] === '未设期限' ? '未设期限' : '办理中未超期') }}
            </span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openDetail(row)">详情/回复</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无公众诉求数据，可先登记诉求记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条公众诉求记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-head">
          <h3>诉求详情 · {{ detail['诉求编号'] }}</h3>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
          <dt>当前状态</dt>
          <dd>{{ detail.status }}</dd>
          <dt>超期判定</dt>
          <dd>
            <span class="overdue-tag" :class="overdueClass(detail)">
              {{ detail['是否超期'] ? '已超期' : (detail['办理期限'] === '未设期限' ? '未设期限，不计超期' : '未超期') }}
            </span>
          </dd>
        </dl>

        <div class="detail-replies">
          <h4>回复记录（重复回复只保留一条）</h4>
          <ul v-if="replyList.length">
            <li v-for="(reply, index) in replyList" :key="`${index}-${reply}`">{{ reply }}</li>
          </ul>
          <p v-else class="empty-state">暂无回复记录</p>
        </div>

        <div class="detail-reply-bar">
          <input
            v-model="replyDraft"
            :disabled="detail.status === '已关闭'"
            :placeholder="detail.status === '已关闭' ? '诉求已关闭，不能再回复' : '填写回复内容后提交'"
          />
          <button
            class="btn primary"
            type="button"
            :disabled="!replyDraft.trim() || detail.status === '已关闭'"
            @click="submitReply"
          >
            提交回复
          </button>
        </div>

        <div class="detail-actions">
          <button class="btn" type="button" :disabled="detail.status === '已关闭'" @click="runAction('受理诉求', detail)">受理诉求</button>
          <button class="btn" type="button" :disabled="detail.status === '已关闭'" @click="runAction('关闭诉求', detail)">关闭诉求</button>
          <span v-if="detailMessage" class="error-text">{{ detailMessage }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | string[] | null>

const ENDPOINT = '/api/complaint'
const columns = ["诉求编号", "诉求来源", "诉求内容", "涉及设施", "受理人员", "处理措施", "办理期限", "诉求状态"]
const actions = ["受理诉求", "提交回复", "关闭诉求"]
const statuses = ["待受理", "办理中", "已回复", "已关闭"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const stats = ref<{ label: string; value: number }[]>([
  { label: '待受理诉求', value: 0 },
  { label: '办理中诉求', value: 0 },
  { label: '超期件数', value: 0 },
])

const detail = ref<Row | null>(null)
const replyDraft = ref('')
const detailMessage = ref('')

const replyList = computed<string[]>(() => {
  const value = detail.value?.['回复记录']
  return Array.isArray(value) ? (value as string[]) : []
})

function overdueClass(row: Row): string {
  if (row['是否超期']) return 'overdue'
  if (row['办理期限'] === '未设期限') return 'no-deadline'
  return 'normal'
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '诉求记录登记入口尚未接入审批流'
}

async function callAction(action: string, entry: Row, extra: Record<string, string> = {}) {
  return request(`${ENDPOINT}/${entry.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action, ...extra } }),
  })
}

async function handleAction(action: string, entry: Row, extra: Record<string, string> = {}) {
  const isDetailAction = detail.value?.id === entry.id
  if (isDetailAction) detailMessage.value = ''
  errorMessage.value = ''
  try {
    const response = await callAction(action, entry, extra)
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '公众诉求动作未生效，请稍后重试')
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '公众诉求操作失败'
    if (isDetailAction) detailMessage.value = message
    else errorMessage.value = message
    return
  }
  await Promise.all([reload(), reloadStats()])
  if (isDetailAction) await refreshDetail()
}

function runAction(action: string, row: Row) {
  void handleAction(action, row)
}

async function submitReply() {
  if (!detail.value || !replyDraft.value.trim()) return
  const content = replyDraft.value.trim()
  replyDraft.value = ''
  await handleAction('提交回复', detail.value, { 回复内容: content })
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('诉求记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '公众诉求列表读取失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const payload = (await response.json()) as Record<string, number>
    stats.value = [
      { label: '待受理诉求', value: payload['待受理诉求'] ?? 0 },
      { label: '办理中诉求', value: payload['办理中诉求'] ?? 0 },
      { label: '超期件数', value: payload['超期件数'] ?? 0 },
    ]
  } catch {
    // 统计读不到时保留上次数据，避免和列表一起空掉
  }
}

async function openDetail(row: Row) {
  detailMessage.value = ''
  replyDraft.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('诉求详情读取失败')
    detail.value = await response.json()
  } catch (error) {
    detailMessage.value = error instanceof Error ? error.message : '诉求详情读取失败'
  }
}

async function refreshDetail() {
  if (!detail.value) return
  const response = await request(`${ENDPOINT}/${detail.value.id}`)
  if (response.ok) detail.value = await response.json()
}

function closeDetail() {
  detail.value = null
  detailMessage.value = ''
  replyDraft.value = ''
}

onMounted(() => {
  void reload()
  void reloadStats()
})
</script>

<style scoped>
.stat-warn .stat-value { color: #b42318; }
.overdue-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  border: 1px solid var(--border);
  white-space: nowrap;
}
.overdue-tag.overdue { color: #b42318; border-color: #f0b4ae; background: #fef3f2; }
.overdue-tag.normal { color: #175cd3; border-color: #b2ccff; background: #eff8ff; }
.overdue-tag.no-deadline { color: var(--muted); background: #f1f5f9; }
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 640px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
}
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 12px 0;
  font-size: 13px;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.detail-replies h4 { font-size: 13px; margin: 12px 0 6px; }
.detail-replies ul { margin: 0; padding-left: 20px; font-size: 13px; }
.detail-replies li { margin-bottom: 4px; }
.detail-reply-bar { display: flex; gap: 8px; margin: 12px 0; }
.detail-reply-bar input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
}
.detail-actions { display: flex; gap: 8px; align-items: center; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
