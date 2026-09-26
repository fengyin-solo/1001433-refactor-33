<template>
  <section class="page" data-module="complaint-reply">
    <header class="page-head">
      <div>
        <h2>诉求回复</h2>
        <p class="page-desc">对办理中的诉求提交回复，已回复的诉求可修正回复内容；同一诉求重复回复只保留最新一条，已关闭诉求不能再回复。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/complaint">诉求受理</RouterLink>
        <RouterLink class="btn" to="/complaint/stats">诉求统计</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待回复（办理中）</span>
        <strong class="stat-value">{{ stats?.by_status['办理中'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已回复</span>
        <strong class="stat-value">{{ stats?.by_status['已回复'] ?? 0 }}</strong>
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
          <option value="">办理中与已回复</option>
          <option value="办理中">办理中</option>
          <option value="已回复">已回复</option>
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
          <th>诉求内容</th>
          <th>办理期限</th>
          <th>诉求状态</th>
          <th>现有回复</th>
          <th>超期</th>
          <th>回复与关闭</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td><RouterLink :to="`/complaint/${row.id}`">{{ row.诉求编号 }}</RouterLink></td>
          <td>{{ row.诉求内容 }}</td>
          <td>{{ row.办理期限 }}</td>
          <td>{{ row.诉求状态 }}</td>
          <td>
            <template v-if="row.replies.length">
              <p class="reply-content">{{ row.replies[0].content }}</p>
              <p class="reply-meta">{{ row.replies[0].replied_at }}</p>
            </template>
            <span v-else class="tag tag-muted">尚未回复</span>
          </td>
          <td>
            <span v-if="row.deadline_missing" class="tag tag-muted">未定期限</span>
            <span v-else-if="row.is_overdue" class="tag tag-danger">超期</span>
            <span v-else class="tag tag-ok">正常</span>
          </td>
          <td>
            <template v-if="row.status === '办理中' || row.status === '已回复'">
              <form class="reply-form" @submit.prevent="submitReply(row)">
                <textarea
                  v-model="drafts[row.id]"
                  rows="2"
                  :placeholder="row.replies.length ? '修正回复内容（覆盖现有一条）' : '填写回复内容'"
                ></textarea>
                <div class="reply-actions">
                  <button class="btn primary" type="submit">{{ row.replies.length ? '更新回复' : '提交回复' }}</button>
                  <button class="btn" type="button" @click="closeRow(row)">关闭诉求</button>
                </div>
              </form>
            </template>
            <span v-else class="tag tag-muted">终态不可操作</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="7" class="empty-state">当前条件下没有需要回复的诉求</td>
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
import { onMounted, reactive, ref } from 'vue'

import { fetchComplaints, fetchComplaintStats, runComplaintAction, type ComplaintRow, type ComplaintStats, type ComplaintStatus } from './shared'

const rows = ref<ComplaintRow[]>([])
const total = ref(0)
const stats = ref<ComplaintStats | null>(null)
const keyword = ref('')
const statusFilter = ref<ComplaintStatus | ''>('')
const overdueOnly = ref(false)
const drafts = reactive<Record<number, string>>({})
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
    rows.value = statusFilter.value
      ? list.rows
      : list.rows.filter((row) => row.status === '办理中' || row.status === '已回复')
    total.value = statusFilter.value ? list.total : rows.value.length
    stats.value = stat
    for (const row of rows.value) {
      if (drafts[row.id] === undefined) drafts[row.id] = row.replies[0]?.content ?? ''
    }
  } catch (error) {
    message.value = error instanceof Error ? error.message : '诉求列表读取失败'
    messageError.value = true
  }
}

async function submitReply(row: ComplaintRow) {
  message.value = ''
  messageError.value = false
  const reply = (drafts[row.id] ?? '').trim()
  if (!reply) {
    message.value = '回复内容不能为空'
    messageError.value = true
    return
  }
  try {
    message.value = await runComplaintAction(row.id, { action: '提交回复', reply })
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '回复提交失败'
    messageError.value = true
  }
}

async function closeRow(row: ComplaintRow) {
  message.value = ''
  messageError.value = false
  try {
    message.value = await runComplaintAction(row.id, { action: '关闭诉求' })
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '关闭失败'
    messageError.value = true
  }
}

onMounted(reload)
</script>
