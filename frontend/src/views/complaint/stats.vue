<template>
  <section class="page" data-module="complaint-stats">
    <header class="page-head">
      <div>
        <h2>诉求超期统计</h2>
        <p class="page-desc">
          统计口径与受理页、回复页完全一致：办理期限当天 18:00 下班时间为截止点，
          已关闭不计超期，未设办理期限统一显示「未定期限」且不算超期。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/complaint">诉求受理</RouterLink>
        <RouterLink class="btn" to="/complaint/reply">前往回复</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value" :class="card.danger ? 'error-text' : ''">{{ card.value }}</strong>
      </article>
    </div>

    <h3 class="section-title">超期诉求明细（{{ overdueRows.length }} 件）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th>诉求编号</th>
          <th>诉求来源</th>
          <th>诉求内容</th>
          <th>办理期限</th>
          <th>诉求状态</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in overdueRows" :key="row.id">
          <td>{{ row.诉求编号 }}</td>
          <td>{{ row.诉求来源 }}</td>
          <td>{{ row.诉求内容 }}</td>
          <td>{{ row.办理期限 }}</td>
          <td>{{ row.诉求状态 }}</td>
          <td><RouterLink class="link" :to="`/complaint/${row.id}`">查看详情</RouterLink></td>
        </tr>
        <tr v-if="!overdueRows.length">
          <td colspan="6" class="empty-state">暂无超期诉求</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>超期件数 {{ stats?.overdue ?? 0 }}，与受理页、回复页一致</span>
      <span v-if="message" class="error-text">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchComplaints, fetchComplaintStats, type ComplaintRow, type ComplaintStats, type ComplaintStatus } from './shared'

const stats = ref<ComplaintStats | null>(null)
const overdueRows = ref<ComplaintRow[]>([])
const message = ref('')

const STATUS_LABELS: ComplaintStatus[] = ['待受理', '办理中', '已回复', '已关闭']

const cards = computed(() => {
  const by = stats.value?.by_status
  const base = STATUS_LABELS.map((label) => ({ label, value: by?.[label] ?? 0, danger: false }))
  return [
    ...base,
    { label: '超期件数', value: stats.value?.overdue ?? 0, danger: true },
    { label: '未定期限（不计超期）', value: stats.value?.deadline_missing ?? 0, danger: false },
  ]
})

async function reload() {
  message.value = ''
  try {
    // 同一份判定：/stats 的数字与 overdue=true 的明细来自同一套后端规则。
    const [stat, list] = await Promise.all([
      fetchComplaintStats(),
      fetchComplaints({ overdue: true }),
    ])
    stats.value = stat
    overdueRows.value = list.rows
    if (stat.overdue !== list.rows.length) {
      message.value = '超期件数与明细数量不一致，请刷新后重试'
    }
  } catch (error) {
    message.value = error instanceof Error ? error.message : '诉求统计读取失败'
  }
}

onMounted(reload)
</script>
