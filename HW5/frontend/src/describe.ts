// Turns raw desk events into what the board shows: per-agent state and plain-English lines.

import type { AgentName, AgentOutput, DeskEvent } from './api'

// Each agent has its own color from the inspiration photo, used on its card, its node in the
// team web, and every hand-off line it sends.
export const AGENTS: { name: AgentName; label: string; role: string; color: string; initials: string }[] = [
  { name: 'boss', label: 'Boss', role: 'Reads the ticket, delegates, makes the final call', color: 'rgb(34, 44, 131)', initials: 'B' },
  { name: 'inventory', label: 'Inventory', role: 'Stock, shortfalls, restock vendors', color: 'rgb(46, 76, 222)', initials: 'IN' },
  { name: 'accounting', label: 'Accounting', role: 'Cash, invoices, margins, approval requests', color: 'rgb(238, 89, 99)', initials: 'AC' },
  { name: 'facilities', label: 'Facilities', role: 'Lease, rent, the shop space', color: 'rgb(214, 51, 108)', initials: 'FA' },
  { name: 'customer_service', label: 'Customer Service', role: 'Drafts customer messages (never sent)', color: 'rgb(124, 77, 196)', initials: 'CS' },
]

export const agentColor = (name: string | null | undefined) => AGENTS.find((a) => a.name === name)?.color ?? 'rgb(179, 179, 179)'

export const agentLabel = (name: string | null | undefined) =>
  AGENTS.find((a) => a.name === name)?.label ?? name ?? 'Desk'

export type FeedKind = 'asked' | 'thinking' | 'doing' | 'saying' | 'problem'

export interface FeedItem {
  key: string
  kind: FeedKind
  text: string
  from?: AgentName | null
  detail?: string
  refused?: boolean
}

export interface Draft {
  audience: string
  recipient: string
  subject: string
  body: string
}

export interface AgentView {
  name: AgentName
  status: 'idle' | 'working' | 'done' | 'problem'
  feed: FeedItem[]
  toolsUsed: string[]
  output?: AgentOutput // latest report
  outputs: AgentOutput[] // every report this agent gave on the ticket
  drafts: Draft[]
  calls: number
}

const money = (n: unknown) =>
  typeof n === 'number' ? `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '?'

type R = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any

const DELEGATE: Record<string, string> = {
  ask_inventory_agent: 'Inventory',
  ask_accounting_agent: 'Accounting',
  ask_facilities_agent: 'Facilities',
  ask_customer_service_agent: 'Customer Service',
}

/** What the agent decided to do next (shown as "thinking" when the model gives no text). */
export function describeIntent(tool: string, args: R): string | null {
  if (tool.startsWith('final_result')) return 'Writing up its report.'
  if (DELEGATE[tool]) return `Handing off to ${DELEGATE[tool]}: “${args.task}”`
  if (tool === 'consult_teammate') return `Checking with ${agentLabel(args.teammate)}: “${args.question}”`
  const pretty = Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' && v.length > 40 ? v.slice(0, 40) + '…' : v}`)
    .join(', ')
  return `Going to call ${tool}(${pretty})`
}

/** One line describing an MCP tool call and its result. */
export function describeTool(tool: string, args: R, result: R): { text: string; refused?: boolean } {
  if (result && result.refused) return { text: `${tool} refused: ${result.reason}`, refused: true }
  switch (tool) {
    case 'get_ticket_with_links': {
      const t = result?.ticket
      if (!t) return { text: `Ticket #${args.ticket_id} not found` }
      const links = [
        result.linked_invoice && `invoice ${result.linked_invoice.id} (${money(result.linked_invoice.amount)}, ${result.linked_invoice.status})`,
        result.linked_lease && `lease ${result.linked_lease.id} (${money(result.linked_lease.monthly_rent)} due ${result.linked_lease.next_due})`,
      ].filter(Boolean)
      return { text: `Read ticket #${t.id} “${t.subject}”${links.length ? ' → ' + links.join(', ') : ''}` }
    }
    case 'check_stock_and_price': {
      const row = result?.requested_size_row
      if (!row) return { text: `${args.sku} ${args.size}: not in inventory` }
      const short = result.shortfall ? `, short ${result.shortfall}` : ''
      return { text: `${args.sku} ${args.size}: ${row.qty} on hand${short} · cost ${money(result.pricing?.unit_cost)} / list ${money(result.pricing?.list_price)}` }
    }
    case 'get_cash_and_obligations': {
      const t = result?.totals ?? {}
      return { text: `Checking ${money(t.cash_on_hand)} · open invoices ${money(t.open_invoices)} · rent ${money(t.next_rent_due)} · left if all paid ${money(t.cash_left_if_all_paid)}` }
    }
    case 'get_vendor_restock_options': {
      const vs: R[] = result?.vendors ?? []
      const blocked = vs.filter((v) => !v.can_ship_new_orders).map((v) => v.name)
      return { text: `${vs.length} vendor(s) checked${blocked.length ? ` · blocked by open invoice: ${blocked.join(', ')}` : ' · all can ship'}` }
    }
    case 'check_margin':
      return { text: `${args.qty ?? 1} × ${money(result?.unit_price)} → margin ${money(result?.margin_per_unit)}/unit (${result?.margin_pct_of_price}%), ${result?.discount_vs_list_pct}% off list` }
    case 'request_payment_approval':
      return { text: `Asked for approval #${result?.approval_id}: ${result?.kind?.replace('_', ' ')} ${money(result?.amount)} (waiting on you)` }
    case 'prepare_purchase_order':
      return { text: `Prepared PO #${result?.approval_id}: ${result?.qty} × ${result?.sku} ${result?.size} from ${result?.vendor}, ${money(result?.estimated_cost)} (waiting on you)` }
    case 'list_approval_requests':
      return { text: `Looked at ${(result?.approvals ?? []).length} approval request(s)` }
    case 'post_draft_to_board':
      return { text: `Drafted a ${args.audience} message to ${args.recipient}: “${args.subject}” (not sent)` }
    case 'read_board':
      return { text: `Read ${(result?.board ?? []).length} board item(s)` }
    case 'update_ticket_status':
      return { text: `Ticket #${result?.ticket_id}: ${result?.old_status} → ${result?.new_status}` }
    case 'list_open_tickets':
      return { text: `Listed ${(result?.tickets ?? []).length} ticket(s)` }
    default:
      return { text: tool }
  }
}

/** Fold one run's events into a view per agent. */
export function buildAgentViews(events: DeskEvent[]): Record<AgentName, AgentView> {
  const views = Object.fromEntries(
    AGENTS.map((a) => [a.name, { name: a.name, status: 'idle', feed: [], toolsUsed: [], drafts: [], outputs: [], calls: 0 }]),
  ) as unknown as Record<AgentName, AgentView>

  for (const e of events) {
    if (!e.agent || !views[e.agent]) continue
    const v = views[e.agent]
    const key = String(e.index)
    switch (e.event) {
      case 'agent_started':
        v.status = 'working'
        v.calls += 1
        v.feed.push({ key, kind: 'asked', from: e.asked_by ?? null, text: e.asked_by ? `${agentLabel(e.asked_by)} asked:` : 'Ticket assigned:', detail: e.task })
        break
      case 'agent_step': {
        ;(e.thoughts ?? []).forEach((t, i) => v.feed.push({ key: `${key}-t${i}`, kind: 'thinking', text: t }))
        if (!(e.thoughts ?? []).length)
          (e.tool_requests ?? []).forEach((r, i) => {
            const text = describeIntent(r.tool, r.args ?? {})
            if (text) v.feed.push({ key: `${key}-r${i}`, kind: 'thinking', text })
          })
        break
      }
      case 'tool_called': {
        const d = describeTool(e.tool ?? '', (e.args ?? {}) as R, (e.result ?? {}) as R)
        v.feed.push({ key, kind: 'doing', text: d.text, refused: d.refused })
        if (e.tool && !v.toolsUsed.includes(e.tool)) v.toolsUsed.push(e.tool)
        const a = (e.args ?? {}) as R
        if (e.tool === 'post_draft_to_board' && !(e.result as R)?.refused)
          v.drafts.push({ audience: a.audience, recipient: a.recipient, subject: a.subject, body: a.body })
        break
      }
      case 'agent_finished':
        v.status = 'done'
        v.output = e.output
        if (e.output) v.outputs.push(e.output)
        v.feed.push({ key, kind: 'saying', text: e.said ?? 'Done.' })
        break
      case 'agent_failed':
      case 'agent_stopped_budget':
        v.status = 'problem'
        v.feed.push({ key, kind: 'problem', text: e.error ?? e.event })
        break
    }
  }
  return views
}

export const statusLabel = (status: string) =>
  ({
    open: 'Open',
    in_progress: 'In progress',
    waiting_on_approval: 'Needs approval',
    waiting_on_vendor: 'Waiting on vendor',
    resolved: 'Complete',
  })[status] ?? status

export const describeApproval = (a: { kind: string; ref_id: number | null; qty: number | null; sku: string | null; size: string | null; vendor_id: number | null }) =>
  a.kind === 'purchase_order'
    ? `Purchase order · ${a.qty} × ${a.sku} ${a.size} (vendor ${a.vendor_id})`
    : a.kind === 'invoice_payment'
      ? `Pay invoice #${a.ref_id}`
      : `Pay rent · lease #${a.ref_id}`

export { money }

export interface Handoff {
  key: string
  order: number
  from: AgentName
  to: AgentName
  task: string
  startIndex: number
  finishIndex: number | null // the event where `to` reported back
  answer?: string
}

/** Every delegation in these events, in order, with when the teammate reported back. */
export function buildHandoffs(events: DeskEvent[]): Handoff[] {
  const handoffs: Handoff[] = []
  const open: Partial<Record<AgentName, Handoff[]>> = {}
  for (const e of events) {
    if (!e.agent) continue
    if (e.event === 'agent_started' && e.asked_by) {
      const h: Handoff = { key: String(e.index), order: handoffs.length + 1, from: e.asked_by, to: e.agent, task: e.task ?? '', startIndex: e.index, finishIndex: null }
      handoffs.push(h)
      ;(open[e.agent] ??= []).push(h)
    } else if (['agent_finished', 'agent_failed', 'agent_stopped_budget'].includes(e.event)) {
      const h = open[e.agent]?.pop()
      if (h) {
        h.finishIndex = e.index
        h.answer = e.said
      }
    }
  }
  return handoffs
}
