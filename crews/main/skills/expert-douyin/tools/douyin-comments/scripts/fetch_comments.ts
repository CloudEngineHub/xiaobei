#!/usr/bin/env -S node --experimental-strip-types
/**
 * fetch_comments.ts — 抖音视频评论抓取（纯 HTTP + cookie + a_bogus 签名）
 *
 * 复用 login-manager 中央存储的 douyin cookie + UA（与 douyin 持久化 session 同一
 * 登录态）和 _shared/douyin-web.ts 的签名请求链路（与 published-track fetch-metrics
 * 取数同源），不启动浏览器。
 *
 * Usage:
 *   node fetch_comments.ts fetch --aweme-id <id> [--limit 40] [--output path/to/comments.md]
 *   node fetch_comments.ts fetch --url "https://www.douyin.com/video/<id>" [--limit 40]
 *   node fetch_comments.ts fetch --url "https://v.douyin.com/xxx" ...   # 短链自动展开
 *
 * Output: JSON 到 stdout（全部评论按热度序 + 点赞排序字段）；--output 时额外落
 * 一份按点赞降序的 markdown 摘要。
 *
 * Exit codes:
 *   0  成功
 *   1  一般错误（参数 / 网络 / 签名不可用）
 *   2  SESSION_EXPIRED — cookie 缺失或失效，调用方走 login-manager 重登
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync } from "fs"
import { dirname, join } from "path"
import { homedir } from "os"

// ─── Types ────────────────────────────────────────────────────────────────

interface CookieRecord { name: string; value: string; domain?: string }

interface SessionData {
  platform: string
  cookies?: CookieRecord[] | string
  user_agent?: string
  updated_at?: string
}

interface DouyinUser {
  nickname?: string
  unique_id?: string
  short_id?: string
}

interface DouyinComment {
  cid?: string
  text?: string
  digg_count?: number
  create_time?: number
  reply_comment_total?: number
  ip_label?: string
  user?: DouyinUser
  sticker?: { content?: string }  // 表情包评论无 text
}

interface CommentListResponse {
  status_code?: number
  comments?: DouyinComment[]
  cursor?: number
  has_more?: number | boolean
  total?: number
}

interface FlatComment {
  cid: string
  text: string
  likeCount: number
  replyCount: number
  userName: string
  ipLabel: string
  createTime: string
}

interface FetchResult {
  ok: boolean
  awemeId: string
  total: number
  fetched: number
  truncated: boolean
  comments: FlatComment[]
  error?: string
}

// ─── Session（与 published-track/scripts/fetch-retro-data.ts 同模式）────────

const SESSIONS_DIR = join(homedir(), ".openclaw", "logins")
const DEFAULT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

function readSession(platform: string): SessionData | null {
  const path = join(SESSIONS_DIR, `${platform}.json`)
  if (!existsSync(path)) return null
  try {
    const raw = JSON.parse(readFileSync(path, "utf-8"))
    // camoufox-cli `cookies export` 写的是裸数组，归一化为 {cookies: [...]}
    if (Array.isArray(raw)) return { platform, cookies: raw } as SessionData
    return raw as SessionData
  } catch {
    return null
  }
}

function readUserAgent(platform: string): string {
  const path = join(SESSIONS_DIR, `${platform}.ua.json`)
  if (!existsSync(path)) return DEFAULT_UA
  try {
    const data = JSON.parse(readFileSync(path, "utf-8")) as { userAgent?: string }
    return data.userAgent || DEFAULT_UA
  } catch {
    return DEFAULT_UA
  }
}

function requireSession(platform: string): SessionData {
  const data = readSession(platform)
  const empty = !data || !data.cookies || (Array.isArray(data.cookies) && data.cookies.length === 0)
  if (empty) {
    process.stderr.write(JSON.stringify({ ok: false, error: "SESSION_EXPIRED", platform }) + "\n")
    process.exit(2)
  }
  return data
}

function parseCookies(raw: CookieRecord[] | string | undefined): Record<string, string> {
  const dict: Record<string, string> = {}
  if (Array.isArray(raw)) {
    for (const c of raw) {
      if (c && typeof c.name === "string" && typeof c.value === "string") {
        dict[c.name] = c.value
      }
    }
  } else if (typeof raw === "string" && raw) {
    for (const item of raw.split(";")) {
      const trimmed = item.trim()
      if (!trimmed || !trimmed.includes("=")) continue
      const [k, ...rest] = trimmed.split("=")
      dict[k.trim()] = rest.join("=").trim()
    }
  }
  return dict
}

function cookieHeader(dict: Record<string, string>): string {
  return Object.entries(dict).map(([k, v]) => `${k}=${v}`).join("; ")
}

// ─── aweme_id 解析 ────────────────────────────────────────────────────────

function extractAwemeId(url: string): string | null {
  const match = url.match(/\/video\/(\d+)/)
  return match ? match[1] : null
}

async function resolveShortLink(url: string): Promise<string> {
  let current = url
  for (let hop = 0; hop < 5; hop++) {
    const resp = await fetch(current, {
      redirect: "manual",
      headers: { "User-Agent": DEFAULT_UA },
      signal: AbortSignal.timeout(15_000),
    })
    const location = resp.headers.get("location")
    if (!location) return current
    current = location.startsWith("http") ? location : new URL(location, current).href
    if (extractAwemeId(current)) return current
  }
  return current
}

async function resolveAwemeId(awemeIdArg: string, urlArg: string): Promise<string> {
  if (awemeIdArg) {
    if (!/^\d+$/.test(awemeIdArg)) {
      throw new Error(`--aweme-id 必须是纯数字: ${awemeIdArg}`)
    }
    return awemeIdArg
  }
  if (!urlArg) throw new Error("需要 --aweme-id 或 --url")
  let url = urlArg
  if (!extractAwemeId(url)) {
    url = await resolveShortLink(url)
  }
  const id = extractAwemeId(url)
  if (!id) throw new Error(`无法从 URL 解析 aweme_id: ${urlArg}`)
  return id
}

// ─── 评论抓取 ─────────────────────────────────────────────────────────────

const COMMENT_URI = "/aweme/v1/web/comment/list/"
const PAGE_SIZE = 20

function flatten(item: DouyinComment): FlatComment {
  const text = item.text || (item.sticker?.content ? `[表情包] ${item.sticker.content}` : "")
  return {
    cid: item.cid || "",
    text,
    likeCount: item.digg_count || 0,
    replyCount: item.reply_comment_total || 0,
    userName: item.user?.nickname || "",
    ipLabel: item.ip_label || "",
    createTime: item.create_time ? new Date(item.create_time * 1000).toISOString().slice(0, 10) : "",
  }
}

async function fetchComments(awemeId: string, limit: number): Promise<FetchResult> {
  const session = requireSession("douyin")
  const cookieStr = cookieHeader(parseCookies(session.cookies))
  const ua = readUserAgent("douyin")
  const { douyinWebGet } = await import("../../../../_shared/douyin-web.ts")

  const comments: FlatComment[] = []
  let cursor = 0
  let total = 0
  let truncated = false

  while (comments.length < limit) {
    const remaining = limit - comments.length
    const count = Math.min(PAGE_SIZE, Math.max(remaining, 1))
    let resp: Awaited<ReturnType<typeof douyinWebGet<CommentListResponse>>> | null = null

    // status_code=8 为间歇鉴权抖动（同 douyin-video-publish work_list 的已知行为），重试 2 次
    for (let attempt = 0; attempt < 3; attempt++) {
      resp = await douyinWebGet<CommentListResponse>(
        COMMENT_URI,
        { aweme_id: awemeId, cursor, count, item_type: 0 },
        cookieStr,
        ua,
      )
      if (resp.data?.status_code !== 8) break
      await new Promise(r => setTimeout(r, 1000 * (attempt + 1)))
    }

    const data = resp?.data
    if (!resp?.ok || !data || data.status_code !== 0) {
      const code = data?.status_code ?? resp?.status ?? "unknown"
      // 登录态失效常见表现为非 0 状态码 + 空评论；首屏即失败按 SESSION_EXPIRED 交重登
      if (comments.length === 0) {
        return { ok: false, awemeId, total: 0, fetched: 0, truncated: false, comments: [], error: `SESSION_EXPIRED(comment list status_code=${code})` }
      }
      truncated = true
      break
    }

    total = data.total || total
    const page = (data.comments || []).map(flatten).filter(c => c.text)
    comments.push(...page)

    const hasMore = Boolean(data.has_more)
    if (!hasMore || page.length === 0) break
    cursor = typeof data.cursor === "number" ? data.cursor : cursor + count
  }

  if (comments.length > limit) {
    comments.length = limit
    truncated = true
  }

  return { ok: true, awemeId, total, fetched: comments.length, truncated, comments }
}

// ─── Markdown 摘要 ────────────────────────────────────────────────────────

function markdownDigest(result: FetchResult): string {
  const sorted = [...result.comments].sort((a, b) => b.likeCount - a.likeCount)
  const lines = [
    `# 抖音评论摘要（aweme_id: ${result.awemeId}）`,
    "",
    `- 抓取时间：${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC`,
    `- 评论总数（平台口径）：${result.total}`,
    `- 本次抓取：${result.fetched} 条${result.truncated ? "（已达 --limit，未抓全）" : ""}`,
    "- 排序：点赞降序",
    "",
    "| # | 点赞 | 回复 | 评论 | 用户 | IP | 日期 |",
    "|---:|---:|---:|------|------|------|------|",
  ]
  sorted.forEach((c, i) => {
    const text = c.text.replace(/\|/g, "\\|").replace(/\n/g, " ")
    lines.push(`| ${i + 1} | ${c.likeCount} | ${c.replyCount} | ${text} | ${c.userName.replace(/\|/g, "\\|")} | ${c.ipLabel} | ${c.createTime} |`)
  })
  lines.push("", "> 读评论动机而不是只数评论数：喜欢内容价值 / 喜欢人物状态 / 喜欢形式设定 / 提出具体问题 / 非恶意吐槽，分别指向不同的可借鉴方向。")
  return lines.join("\n") + "\n"
}

// ─── Main ─────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2)
  const command = args[0]

  if (command !== "fetch") {
    process.stderr.write("用法: douyin-comments fetch --aweme-id <id> | --url <视频链接> [--limit 40] [--output comments.md]\n")
    process.exit(1)
  }

  let awemeIdArg = ""
  let urlArg = ""
  let limit = 40
  let output = ""

  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--aweme-id" && args[i + 1]) awemeIdArg = args[++i]
    else if (args[i] === "--url" && args[i + 1]) urlArg = args[++i]
    else if (args[i] === "--limit" && args[i + 1]) limit = parseInt(args[++i], 10)
    else if (args[i] === "--output" && args[i + 1]) output = args[++i]
  }

  if (!Number.isFinite(limit) || limit <= 0 || limit > 200) {
    process.stderr.write("--limit 必须是 1-200 的整数（避免批量请求触风控）\n")
    process.exit(1)
  }

  const awemeId = await resolveAwemeId(awemeIdArg, urlArg)
  console.error(`  → 抓取评论 aweme_id=${awemeId} limit=${limit}`)
  const result = await fetchComments(awemeId, limit)

  if (!result.ok) {
    if (result.error?.startsWith("SESSION_EXPIRED")) {
      process.stderr.write(JSON.stringify({ ok: false, error: "SESSION_EXPIRED", platform: "douyin" }) + "\n")
      process.exit(2)
    }
    process.stderr.write(`❌ ${result.error}\n`)
    process.exit(1)
  }

  console.error(`  ✓ 抓到 ${result.fetched}/${result.total} 条评论`)

  if (output) {
    mkdirSync(dirname(output), { recursive: true })
    writeFileSync(output, markdownDigest(result), "utf-8")
    console.error(`  ✓ 摘要已写入 ${output}`)
  }

  process.stdout.write(JSON.stringify(result, null, 2) + "\n")
}

main().catch(e => {
  process.stderr.write(`❌ ${e}\n`)
  process.exit(1)
})
