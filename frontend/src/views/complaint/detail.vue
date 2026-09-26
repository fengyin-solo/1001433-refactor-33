<template>
  <section class="page" data-module="complaint-detail">
    <header class="page-head">
      <div>
        <h2>诉求详情</h2>
        <p class="page-desc">办理期限与超期结论由系统统一给出，与受理页、回复页、统计页保持一致。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/complaint">返回受理</RouterLink>
        <RouterLink class="btn" to="/complaint/stats">返回统计</RouterLink>
      </div>
    </header>

    <article v-if="row" class="detail-card">
      <div class="detail-banner">
        <span class="tag" :class="row.deadline_missing ? 'tag-muted' : row.is_overdue ? 'tag-danger' : 'tag-ok'">
          {{ row.deadline_missing ? '未定期限' : row.is_overdue ? '已超期' : '未超期' }}
        </span>
        <span class="tag" :class="row.status === '已关闭' ? 'tag-muted' : 'tag-ok'">{{ row.诉求状态 }}</span>
      </div>
      <dl class="detail-grid">
        <template v-for="item in fields" :key="item.key">
          <dt>{{ item.label }}</dt>
          <dd>{{ display(item.key) }}</dd>
        </template>
        <dt>办理期限</dt>
        <dd>
          {{ row.办理期限 }}
          <span v-if="!row.deadline_missing" class="reply-meta">（截止至期限当天 18:00）</span>
        </dd>
      </dl>

      <h3 class="section-title">回复记录（{{ row.replies.length }}）</h3>
      <ul v-if="row.replies.length" class="reply-list">
        <li v-for="reply in row.replies" :key="reply.replied_at">
          <p class="reply-content">{{ reply.content }}</p>
          <p class="reply-meta">{{ reply.replied_at }}</p>
        </li>
      </ul>
      <p v-else class="empty-inline">暂无回复</p>
    </article>

    <p v-else-if="message" class="error-text">{{ message }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'
import type { ComplaintRow } from './shared'

const route = useRoute()
const row = ref<ComplaintRow | null>(null)
const message = ref('')

const fields = [
  { key: '诉求编号', label: '诉求编号' },
  { key: '诉求来源', label: '诉求来源' },
  { key: '诉求内容', label: '诉求内容' },
  { key: '涉及设施', label: '涉及设施' },
  { key: '受理人员', label: '受理人员' },
  { key: '处理措施', label: '处理措施' },
] as const

function display(key: string): string {
  const value = row.value ? (row.value as unknown as Record<string, string | null>)[key] : null
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

onMounted(async () => {
  const id = route.params.id
  try {
    const res = await request(`/api/complaint/${id}`)
    if (!res.ok) throw new Error('诉求详情读取失败')
    row.value = (await res.json()) as ComplaintRow
  } catch (error) {
    message.value = error instanceof Error ? error.message : '诉求详情读取失败'
  }
})
</script>
