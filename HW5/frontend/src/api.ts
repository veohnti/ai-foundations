// Client for the Campus Customs desk API (backend/main.py, routes a–f).

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  created_at: string
  is_open: boolean
  is_resolved: boolean
}

export interface Approval {
  id: number
  kind: 'invoice_payment' | 'rent_payment' | 'purchase_order'
  ticket_id: number | null
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  account: string | null
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'denied' | 'paid'
  decided_by: string | null
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  desk_date_today: string
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  mode: string
  state: 'running' | 'finished' | 'stopped' | 'failed'
  decision?: BossDecision | null
  error?: string
}

export interface Fact { source_tool: string; detail: string }

export interface BoardItem {
  id: number
  ticket_id: number | null
  author_agent: AgentName
  audience: 'customer' | 'vendor' | 'landlord' | 'internal'
  recipient: string
  subject: string
  body: string
  status: string
  created_at: string
}

export interface BossDecision {
  ticket_id: number
  final_decision: string
  new_status: string
  delegated_to: string[]
  pending_human_approvals: number[]
  board_draft_ids: number[]
  next_steps: string[]
  facts_relied_on: Fact[]
}

export interface AgentOutput {
  summary?: string
  final_decision?: string
  recommendation?: string
  actions_taken?: string[]
  blockers?: string[]
  approval_ids?: number[]
  board_draft_ids?: number[]
  facts?: Fact[]
  facts_relied_on?: Fact[]
  next_steps?: string[]
  new_status?: string
}

export interface DeskEvent {
  index: number
  ts: string
  run_id: string
  event: string
  agent: AgentName | null
  ticket_id: number | null
  task?: string
  asked_by?: AgentName | null
  thoughts?: string[]
  tool_requests?: { tool: string; args: Record<string, unknown> }[]
  tool?: string
  args?: Record<string, unknown>
  result?: unknown
  said?: string
  output?: AgentOutput
  tools_used?: string[]
  error?: string
  state?: string
  [key: string]: unknown
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  tickets: () => call<{ desk_date_today: string; tickets: Ticket[] }>('/tickets'),
  runTicket: (id: number) =>
    call<{ run_id: string; mode: string }>(`/tickets/${id}/run`, { method: 'POST' }),
  run: (runId: string) => call<RunInfo>(`/runs/${runId}`),
  events: (params: { run_id?: string; ticket_id?: number; after?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return call<{ events: DeskEvent[]; next: number; runs: RunInfo[] }>(`/events?${q}`)
  },
  approvals: (status?: string) =>
    call<{ approvals: Approval[] }>(`/approvals${status ? `?status=${status}` : ''}`),
  approve: (id: number) => call<Record<string, unknown>>(`/approvals/${id}/approve`, { method: 'POST', body: '{}' }),
  deny: (id: number) => call<Record<string, unknown>>(`/approvals/${id}/deny`, { method: 'POST', body: '{}' }),
  cash: () => call<Cash>('/cash'),
  board: () => call<{ board: BoardItem[] }>('/board'),
  reset: () => call<Record<string, unknown>>('/reset', { method: 'POST' }),
}
