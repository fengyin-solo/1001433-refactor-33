/** 公众诉求的取数与动作入口。
 *
 * 超期与否一律以后端 is_overdue 为准，受理页、回复页、统计页都从这里取数，
 * 前端不再各自比较日期，避免三处口径打架。
 */
import { request } from '@/api/client'

const ENDPOINT = '/api/complaint'

export type ComplaintStatus = '待受理' | '办理中' | '已回复' | '已关闭'

export interface ComplaintReply {
  content: string
  replied_at: string
}

export interface ComplaintRow {
  id: number
  诉求编号: string
  诉求来源: string
  诉求内容: string
  涉及设施: string | null
  受理人员: string | null
  处理措施: string | null
  办理期限: string
  诉求状态: ComplaintStatus
  status: ComplaintStatus
  pending: boolean
  is_overdue: boolean
  deadline_missing: boolean
  replies: ComplaintReply[]
}

export interface ComplaintStats {
  total: number
  by_status: Record<ComplaintStatus, number>
  overdue: number
  overdue_ids: number[]
  deadline_missing: number
}

interface PageResult<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ListParams {
  keyword?: string
  status?: ComplaintStatus | ''
  overdue?: boolean
}

export async function fetchComplaints(params: ListParams = {}): Promise<{ rows: ComplaintRow[]; total: number }> {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.status) query.set('status', params.status)
  if (params.overdue) query.set('overdue', 'true')
  const payload = await request(`${ENDPOINT}?${query.toString()}`).then((res) => {
    if (!res.ok) throw new Error('诉求列表读取失败')
    return res.json() as Promise<PageResult<ComplaintRow>>
  })
  return { rows: payload.items ?? [], total: payload.total ?? 0 }
}

export async function fetchComplaintStats(): Promise<ComplaintStats> {
  return request(`${ENDPOINT}/stats`).then((res) => {
    if (!res.ok) throw new Error('诉求统计读取失败')
    return res.json() as Promise<ComplaintStats>
  })
}

export interface ActionParams {
  action: '受理诉求' | '提交回复' | '关闭诉求'
  reply?: string
  operator?: string
}

export async function runComplaintAction(id: number, params: ActionParams): Promise<string> {
  const res = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error('诉求动作未生效，请稍后重试')
  const payload = (await res.json()) as { ok: boolean; message: string }
  if (!payload.ok) throw new Error(payload.message || '诉求操作未生效')
  return payload.message
}
