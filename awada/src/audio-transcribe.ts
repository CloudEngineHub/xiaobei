/**
 * Audio transcription via 公共 ASR 路由（与 crews/main/skills/_shared/asr.py 同优先级）。
 *
 * 供应商优先级（2026-09 拍板，凭据在哪家走哪家）：
 *   1. 火山录音文件极速版 — VOLC_ASR_APP_ID+VOLC_ASR_ACCESS_KEY（旧控制台双头）
 *      或 VOLC_ASR_APP_KEY（新控制台单头）
 *      POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
 *   2. 百炼业务空间 — WORKSPACE_ID + MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY
 *      POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
 *   3. 百炼 agent plan — AWK_API_KEY
 *      POST https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
 *      模型 qwen-audio-3.0-asr-flash（BAILIAN_ASR_MODEL 可覆盖）
 *
 * 某家失败自动落下一家；全部失败时 error 汇总各家原因。
 * 百炼以 base64 data URI 直传（编码后 ≤10MB，语音消息远低于此限）。
 */

const VOLC_ASR_ENDPOINT =
  "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash";
const BAILIAN_WS_BASE_TEMPLATE = "https://{wsid}.cn-beijing.maas.aliyuncs.com/api/v1";
const BAILIAN_AGENT_PLAN_BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1";
const BAILIAN_ASR_PATH = "/services/aigc/multimodal-generation/generation";
const BAILIAN_DEFAULT_ASR_MODEL = "qwen-audio-3.0-asr-flash";
const MAX_BAILIAN_B64_BYTES = 9 * 1024 * 1024;

const AUDIO_MIME_BY_EXT: Record<string, string> = {
  mp3: "audio/mpeg",
  wav: "audio/x-wav",
  ogg: "audio/ogg",
  opus: "audio/opus",
  m4a: "audio/mp4",
  aac: "audio/aac",
  flac: "audio/flac",
  amr: "audio/amr",
};

export type TranscribeResult =
  | { ok: true; text: string }
  | { ok: false; error: string };

interface BailianEndpoint {
  base: string;
  apiKey: string;
  mode: "workspace" | "agent-plan";
}

function audioFormatHint(fileName: string): string {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  return ext in AUDIO_MIME_BY_EXT ? ext : "wav";
}

function listBailianEndpoints(): BailianEndpoint[] {
  const endpoints: BailianEndpoint[] = [];
  const wsid = process.env.WORKSPACE_ID?.trim();
  if (wsid) {
    const key =
      process.env.MODELSTUDIO_API_KEY?.trim() ||
      process.env.DASHSCOPE_API_KEY?.trim();
    if (key) {
      endpoints.push({
        base: BAILIAN_WS_BASE_TEMPLATE.replace("{wsid}", wsid),
        apiKey: key,
        mode: "workspace",
      });
    }
  }
  const awkKey = process.env.AWK_API_KEY?.trim();
  if (awkKey) {
    endpoints.push({ base: BAILIAN_AGENT_PLAN_BASE, apiKey: awkKey, mode: "agent-plan" });
  }
  return endpoints;
}

async function transcribeVolc(
  audioBuffer: Buffer,
  fileName: string,
): Promise<TranscribeResult> {
  const appId = process.env.VOLC_ASR_APP_ID?.trim();
  const accessKey = process.env.VOLC_ASR_ACCESS_KEY?.trim();
  const appKey = process.env.VOLC_ASR_APP_KEY?.trim();
  const resourceId =
    process.env.VOLC_ASR_RESOURCE_ID?.trim() || "volc.bigasr.auc_turbo";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Api-Resource-Id": resourceId,
    "X-Api-Request-Id": crypto.randomUUID(),
    "X-Api-Sequence": "-1",
  };
  let uid: string;
  if (appId && accessKey) {
    headers["X-Api-App-Key"] = appId;
    headers["X-Api-Access-Key"] = accessKey;
    uid = appId;
  } else if (appKey) {
    headers["X-Api-Key"] = appKey;
    uid = appKey;
  } else {
    return { ok: false, error: "火山 ASR 凭据未配置" };
  }

  const body = {
    user: { uid },
    audio: {
      data: audioBuffer.toString("base64"),
      format: audioFormatHint(fileName),
    },
    request: {
      model_name: "bigmodel",
      show_utterances: false,
      enable_itn: true,
      enable_punc: true,
    },
  };

  try {
    const res = await fetch(VOLC_ASR_ENDPOINT, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const status = res.headers.get("X-Api-Status-Code") ?? "";
    if (status !== "20000000") {
      const msg = res.headers.get("X-Api-Message") ?? "";
      const snippet = (await res.text().catch(() => "")).slice(0, 200);
      return { ok: false, error: `火山 ASR 失败 (status=${status}, msg=${msg}): ${snippet}` };
    }
    const json = (await res.json()) as { result?: { text?: string } };
    const text = json.result?.text?.trim() ?? "";
    if (!text) {
      return { ok: false, error: "火山 ASR 返回空文本" };
    }
    return { ok: true, text };
  } catch (err) {
    return { ok: false, error: `火山 ASR 请求失败: ${String(err)}` };
  }
}

async function transcribeBailian(
  audioBuffer: Buffer,
  fileName: string,
  endpoint: BailianEndpoint,
): Promise<TranscribeResult> {
  if (audioBuffer.length * (4 / 3) > MAX_BAILIAN_B64_BYTES) {
    return {
      ok: false,
      error: `音频 ${audioBuffer.length} 字节超百炼 base64 上限（10MB）`,
    };
  }
  const fmt = audioFormatHint(fileName);
  const mime = AUDIO_MIME_BY_EXT[fmt] ?? "audio/x-wav";
  const model =
    process.env.BAILIAN_ASR_MODEL?.trim() || BAILIAN_DEFAULT_ASR_MODEL;

  const body = {
    model,
    input: {
      messages: [
        {
          role: "user",
          content: [
            {
              type: "input_audio",
              input_audio: {
                data: `data:${mime};base64,${audioBuffer.toString("base64")}`,
              },
            },
          ],
        },
      ],
    },
    parameters: { format: fmt },
  };

  try {
    const res = await fetch(`${endpoint.base}${BAILIAN_ASR_PATH}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${endpoint.apiKey}`,
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const snippet = (await res.text().catch(() => "")).slice(0, 200);
      return {
        ok: false,
        error: `百炼 ASR 失败 (${endpoint.mode}, HTTP ${res.status}): ${snippet}`,
      };
    }
    const json = (await res.json()) as { output?: { text?: string } };
    const text = json.output?.text?.trim() ?? "";
    if (!text) {
      return { ok: false, error: `百炼 ASR 返回空文本 (${endpoint.mode})` };
    }
    return { ok: true, text };
  } catch (err) {
    return { ok: false, error: `百炼 ASR 请求失败 (${endpoint.mode}): ${String(err)}` };
  }
}

function volcConfigured(): boolean {
  const appId = process.env.VOLC_ASR_APP_ID?.trim();
  const accessKey = process.env.VOLC_ASR_ACCESS_KEY?.trim();
  const appKey = process.env.VOLC_ASR_APP_KEY?.trim();
  return Boolean((appId && accessKey) || appKey);
}

/**
 * Transcribe an audio buffer: 火山 → 百炼业务空间 → 百炼 agent plan 依次尝试。
 */
export async function transcribeAudio(
  audioBuffer: Buffer,
  fileName: string,
): Promise<TranscribeResult> {
  const errors: string[] = [];

  if (volcConfigured()) {
    const result = await transcribeVolc(audioBuffer, fileName);
    if (result.ok) {
      return result;
    }
    errors.push(`火山: ${result.error}`);
  }

  for (const endpoint of listBailianEndpoints()) {
    const result = await transcribeBailian(audioBuffer, fileName, endpoint);
    if (result.ok) {
      return result;
    }
    errors.push(`百炼(${endpoint.mode}): ${result.error}`);
  }

  if (errors.length === 0) {
    return {
      ok: false,
      error:
        "ASR 凭证未配置：需 VOLC_ASR_APP_ID+VOLC_ASR_ACCESS_KEY 或 VOLC_ASR_APP_KEY（火山），" +
        "或 WORKSPACE_ID+MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY（百炼业务空间），" +
        "或 AWK_API_KEY（百炼 agent plan）",
    };
  }
  return { ok: false, error: errors.join(" | ") };
}

/**
 * Fetch audio content from a URL and return as Buffer.
 */
export async function fetchAudioBuffer(url: string): Promise<Buffer> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch audio: ${res.status} ${res.statusText}`);
  }
  return Buffer.from(await res.arrayBuffer());
}
