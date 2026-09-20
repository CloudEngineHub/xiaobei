/**
 * douyin-web.ts — 抖音 web API 统一请求入口（a_bogus 走 relay）
 *
 * 抽自 viral-chaser platforms/douyin.ts，供 viral-chaser / published-track 共用。
 * 封装 COMMON_PARAMS + webid + msToken + verifyFp + fp + a_bogus 签名 + fetch，
 * 消费方只需给 uri / extraParams / cookieStr / ua。
 *
 * 关键：抖音 Janus 网关要求请求带全套 COMMON_PARAMS（device_platform / aid / channel /
 * version_code / browser_* / …）+ webid + verifyFp + fp，缺则 404 Unsupported path(Janus)
 * 或 200 空体。早期 published-track fetchDouyin 只发 aweme_id+msToken+a_bogus，故长期取不到数。
 */

import { douyinSign } from "./relay-sign.ts"

const DOUYIN_API = "https://www.douyin.com"
export const DOUYIN_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
const WEBID_URL = "https://mcs.zijieapi.com/webid?aid=6383&sdk_version=5.1.18_zip&device_platform=web"

// ─── Token helpers ──────────────────────────────────────────────────────────

// Douyin web detail endpoint accepts a random msToken. Real mssdk.bytedance.com
// signing (encrypted strData via mssdk wasm) is not implemented — the random token
// below is the intended path here, not a fallback.
export function genMsToken(_ua?: string): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
  let token = ""
  for (let i = 0; i < 126; i++) token += chars[Math.floor(Math.random() * chars.length)]
  return token + "=="
}

function genWebIdLocal(): string {
  function e(t?: number): string {
    if (t !== undefined) return String(t ^ (Math.floor(16 * Math.random()) >> (t / 4)))
    return "10000000-1000-4000-8000-100000000000"
  }
  return e().replace(/[018]/g, x => e(parseInt(x))).replace(/-/g, "").slice(0, 19)
}

export async function getWebId(ua: string): Promise<string> {
  try {
    const resp = await fetch(WEBID_URL, {
      method: "POST",
      headers: { "User-Agent": ua, "Content-Type": "application/json; charset=UTF-8", "Referer": "https://www.douyin.com/" },
      body: JSON.stringify({ app_id: 6383, referer: "https://www.douyin.com/", url: "https://www.douyin.com/", user_agent: ua, user_unique_id: "" }),
      signal: AbortSignal.timeout(5_000),
    })
    const data = await resp.json() as { web_id?: string }
    if (data.web_id) return data.web_id
  } catch { /* fallback */ }
  return genWebIdLocal()
}

export function genVerifyFp(): string {
  const base = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
  let ms = Date.now()
  let r = ""
  while (ms > 0) { const rem = ms % 36; r = (rem < 10 ? String(rem) : String.fromCharCode(87 + rem)) + r; ms = Math.floor(ms / 36) }
  const o = Array(36).fill("")
  o[8] = o[13] = o[18] = o[23] = "_"; o[14] = "4"
  for (let i = 0; i < 36; i++) if (!o[i]) { let n = Math.floor(Math.random() * 62); if (i === 19) n = (3 & n) | 8; o[i] = base[n] }
  return "verify_" + r + "_" + o.join("")
}

// ─── Common request params ──────────────────────────────────────────────────

export const COMMON_PARAMS: Record<string, string | number> = {
  device_platform: "webapp", aid: "6383", channel: "channel_pc_web",
  publish_video_strategy_type: 2, update_version_code: 170400, pc_client_type: 1,
  version_code: 170400, version_name: "17.4.0", cookie_enabled: "true",
  screen_width: 2560, screen_height: 1440, browser_language: "zh-CN",
  browser_platform: "MacIntel", browser_name: "Chrome", browser_version: "127.0.0.0",
  browser_online: "true", engine_name: "Blink", engine_version: "127.0.0.0",
  os_name: "Mac+OS", os_version: "10.15.7", cpu_core_num: 8, device_memory: 8,
  platform: "PC", downlink: 4.45, effective_type: "4g", round_trip_time: 100,
}

// ─── Signed GET（a_bogus 走 relay）──────────────────────────────────────────

export interface DouyinWebGetResult<T = unknown> {
  status: number
  ok: boolean
  data: T | null
  /** 原始响应体（JSON.parse 失败时用于诊断） */
  text: string
}

/**
 * 发起抖音 web API 签名 GET。
 * @param uri    路径，如 `/aweme/v1/web/aweme/detail/`
 * @param extraParams 业务参数，如 `{ aweme_id }` / `{ sec_uid, count, max_cursor }`
 * @param cookieStr   Cookie 头值（可空，但 detail/post 等接口无 cookie 多半 200 空体）
 * @param ua          User-Agent（缺省 DOUYIN_UA）
 */
export async function douyinWebGet<T = unknown>(
  uri: string,
  extraParams: Record<string, string | number>,
  cookieStr: string,
  ua: string = DOUYIN_UA,
): Promise<DouyinWebGetResult<T>> {
  const [msToken, webid, verifyFp] = await Promise.all([
    genMsToken(ua), getWebId(ua), Promise.resolve(genVerifyFp()),
  ])

  const allParams: Record<string, string> = {}
  for (const [k, v] of Object.entries({ ...COMMON_PARAMS, ...extraParams })) {
    allParams[k] = String(v)
  }
  allParams["webid"] = webid
  allParams["msToken"] = msToken
  allParams["verifyFp"] = verifyFp
  allParams["fp"] = verifyFp

  const queryString = new URLSearchParams(allParams).toString()
  const aBogus = await douyinSign({ queryString, postData: "", ua })
  allParams["a_bogus"] = aBogus

  const fullUrl = `${DOUYIN_API}${uri}?${new URLSearchParams(allParams).toString()}`

  const resp = await fetch(fullUrl, {
    headers: {
      "Cookie": cookieStr,
      "User-Agent": ua,
      "Referer": "https://www.douyin.com/",
      "Accept": "application/json, text/plain, */*",
      "Accept-Language": "zh-CN,zh;q=0.9",
    },
    signal: AbortSignal.timeout(30_000),
  })
  const text = await resp.text()
  let data: T | null = null
  try { data = JSON.parse(text) as T } catch { /* 非 JSON，交消费方看 text */ }
  return { status: resp.status, ok: resp.ok, data, text }
}

// ─── 创作侧 item/list（creator 域，cookie-only，无需 a_bogus）────────────────
//
// 借鉴 OpenCLI #2307（2026-08 实测）：`item_analysis/metrics_trend` 端点已下线（全量
// status_code 4），替代端点 `web/api/creator/item/list` 是创作侧每作品指标的家——
// 26 字段深指标（view_count / bounce_rate_2s / completion_rate_5s / avg_view_second /
// cover_show / cover_click_rate / fan_view_proportion / subscribe_count …），
// 视频 + 图文(note) 作品都在列表里。公开侧 aweme/detail 的 play_count 恒为 0
// （播放量仅创作者可见），view_count 是播放量的唯一来源。
// creator 域 janus/api 只要 cookie（同 work_list 先例：publish_douyin.py 页内
// credentials:'include' fetch，无签名），raw HTTP 带 .douyin.com cookie 即可。

const CREATOR_ITEM_LIST_URL = "https://creator.douyin.com/web/api/creator/item/list"
const ITEM_LIST_PAGE_SIZE = 50
/** 游标遍历上限：500 个作品内找不到即放弃（按发布时间倒序，新作品必在前几页） */
const ITEM_LIST_MAX_HOPS = 10
/** 创作侧 API 间歇鉴权抖动（同 work_list status_code=8 先例），短等纯重试 */
const ITEM_LIST_AUTH_RETRIES = 3

/**
 * id 匹配带数值比较兜底：item/list 把 work id 序列化成 JSON number，JSON.parse
 * 已按 IEEE-754 精度舍入（19 位 aweme_id 必中），字符串比较会全部 miss。
 * （借鉴 OpenCLI sameAwemeId。）
 */
export function sameAwemeId(value: unknown, target: string): boolean {
  if (value == null) return false
  const source = String(value)
  if (source === target) return true
  return /^\d+$/.test(source) && Number(source) === Number(target)
}

/** item.metrics 值是字符串数字（'1173' / '0.288638'），归一化为 number */
function normalizeMetrics(raw: unknown): Record<string, number> {
  const out: Record<string, number> = {}
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return out
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    const n = typeof v === "number" ? v : parseFloat(String(v ?? ""))
    if (Number.isFinite(n)) out[k] = n
  }
  return out
}

export interface DouyinCreatorItem {
  /** 归一化数值指标（键为平台原名：view_count / completion_rate_5s / …） */
  metrics: Record<string, number>
  /** 审核状态（fields=review） */
  review?: string
  /** 可见性（fields=visibility） */
  visibility?: string
}

/**
 * 遍历创作侧 item/list 游标，按 aweme_id 匹配单个作品的深指标。
 * @returns 匹配作品；列表遍历尽未找到返回 null；鉴权持续失败抛错（交消费方决定降级）。
 */
export async function douyinCreatorItem(
  awemeId: string,
  cookieStr: string,
  ua: string = DOUYIN_UA,
): Promise<DouyinCreatorItem | null> {
  let cursor: number | undefined
  for (let hop = 0; hop < ITEM_LIST_MAX_HOPS; hop++) {
    const params = new URLSearchParams({
      count: String(ITEM_LIST_PAGE_SIZE),
      order_by: "1",
      fields: "metrics,review,visibility",
      need_cooperation: "true",
      need_long_article: "true",
    })
    if (cursor !== undefined) params.set("max_cursor", String(cursor))

    let data: any = null
    let ok = false
    for (let attempt = 1; attempt <= ITEM_LIST_AUTH_RETRIES && !ok; attempt++) {
      const resp = await fetch(`${CREATOR_ITEM_LIST_URL}?${params.toString()}`, {
        headers: {
          "Cookie": cookieStr,
          "User-Agent": ua,
          "Referer": "https://creator.douyin.com/",
          "Accept": "application/json, text/plain, */*",
          "Accept-Language": "zh-CN,zh;q=0.9",
        },
        signal: AbortSignal.timeout(30_000),
      })
      const text = await resp.text()
      try { data = JSON.parse(text) } catch { data = null }
      // 间歇鉴权抖动：sc != 0 / 非 JSON 短等重试（同 work_list sc=8 先例，同页连发就稳）
      const sc = data?.status_code
      ok = resp.ok && data != null && (typeof sc !== "number" || sc === 0)
      if (!ok && attempt < ITEM_LIST_AUTH_RETRIES) await new Promise(r => setTimeout(r, 2_000))
    }
    if (!ok) {
      const sc = data?.status_code
      throw new Error(`creator item/list 失败（status_code=${sc ?? "?"}——鉴权持续抖动或 cookie 失效）`)
    }

    const items = (data.items ?? []) as Array<Record<string, unknown>>
    const hit = items.find(it => sameAwemeId(it.id, awemeId))
    if (hit) {
      const review = hit.review
      const visibility = hit.visibility
      return {
        metrics: normalizeMetrics(hit.metrics),
        review: typeof review === "string" ? review : review == null ? undefined : String(review),
        visibility: typeof visibility === "string" ? visibility : visibility == null ? undefined : String(visibility),
      }
    }

    const nextCursor = data.max_cursor
    if (
      !data.has_more ||
      nextCursor === undefined || nextCursor === null ||
      (cursor !== undefined && String(nextCursor) === String(cursor))
    ) {
      return null
    }
    cursor = Number(nextCursor)
  }
  return null
}
