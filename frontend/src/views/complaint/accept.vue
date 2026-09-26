<template>
  <section class="page" data-module="complaint-accept">
    <header class="page-head">
      <div>
        <h2>诉求受理</h2>
        <p class="page-desc">对待受理诉求进行受理，对办理中诉求跟踪进度。超期与否以办理期限当天 18:00 下班时间为准，由系统统一判定。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/complaint/reply">前往回复</RouterLink>
        <RouterLink class="btn" to="/complaint/stats">诉求统计</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待受理</span>
        <strong class="stat-value">{{ stats?.by_status['待受理'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">办理中</span>
        <strong class="stat-value">{{ stats?.by_status['办理中'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">超期件数（与统计同源）</span>
        <strong class="stat-value" :class="{ 'error-text': (stats?.overdue ?? 0) > 0 }">{{ stats?.overdue ?? 0 }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>诉求编号</span>
        <input v-model="keyword" placeholder="按诉求编号检索" />
      </label>
      <label class="filter-item">
        <span>诉求状态</span>
        <select v-model="statusFilter">
          <option value="">待受理与办理中</option>
          <option value="待受理">待受理</option>
          <option value="办理中">办理中</option>
        </select>
      </label>
      <label class="filter-item">
        <span>&nbsp;</span>
        <label class="inline-check">
          <input v-model="overdueOnly" type="checkbox" /> 只看超期
        </label>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>诉求编号</th>
          <th>诉求来源</th>
          <th>诉求内容</th>
          <th>涉及设施</th>
          <th>办理期限</th>
          <th>诉求状态</th>
          <th>超期</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td><RouterLink :to="`/complaint/${row.id}`">{{ row.诉求编号 }}</RouterLink></td>
          <td>{{ row.诉求来源 }}</td>
          <td>{{ row.诉求内容 }}</td>
          <td>{{ row.涉及设施 ?? '—' }}</td>
          <td>{{ row.办理期限 }}</td>
          <td>{{ row.诉求状态 }}</td>
          <td>
            <span v-if="row.deadline_missing" class="tag tag-muted">未定期限</span>
            <span v-else-if="row.is_overdue" class="tag tag-danger">超期</span>
            <span v-else class="tag tag-ok">正常</span>
          </td>
          <td class="row-actions">
            <button
              v-if="row.status === '待受理'"
              class="link"
              type="button"
              @click="accept(row)"
            >受理诉求</button>
            <RouterLink v-if="row.status === '办理中'" class="link" to="/complaint/reply">去回复</RouterLink>
            <RouterLink class="link" :to="`/complaint/${row.id}`">详情</RouterLink>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="8" class="empty-state">当前条件下没有待受理或办理中的诉求</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条诉求</span>
      <span v-if="message" :class="messageError ? 'error-text' : 'ok-text'">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchComplaints, fetchComplaintStats, runComplaintAction, type ComplaintRow, type ComplaintStats, type ComplaintStatus } from './shared'

const rows = ref<ComplaintRow[]>([])
const total = ref(0)
const stats = ref<ComplaintStats | null>(null)
const keyword = ref('')
const statusFilter = ref<ComplaintStatus | ''>('')
const overdueOnly = ref(false)
const message = ref('')
const messageError = ref(false)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  overdueOnly.value = false
  void reload()
}

async function reload() {
  message.value = ''
  try {
    const [list, stat] = await Promise.all([
      fetchComplaints({
        keyword: keyword.value,
        status: statusFilter.value,
        overdue: overdueOnly.value,
      }),
      fetchComplaintStats(),
    ])
    // 受理页只看待受理与办理中；具体状态筛选时以筛选值为准。
    rows.value = statusFilter.value ? list.rows : list.rows.filter((row) => row.status === '待受理' || row.status === '办理中')
    total.value = statusFilter.value ? list.total : rows.value.length
    stats.value = stat
  } catch (error) {
    message.value = error instanceof Error ? error.message : '诉求列表读取失败'
    messageError.value = true
  }
}

async function accept(row: ComplaintRow) {
  message.value = ''
  messageError.value = false
  try {
    message.value = await runComplaintAction(row.id, { action: '受理诉求' })
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '受理失败'
    messageError.value = true
  }
}

onMounted(reload)
</script>
