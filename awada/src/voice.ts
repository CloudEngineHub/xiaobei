import { mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { resolvePreferredOpenClawTmpDir } from "openclaw/plugin-sdk/temp-path";

const SAMPLE_RATE = 24_000;
export function pcmToWav(pcm: Uint8Array): Buffer {
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(pcm.byteLength + 36, 4);
  header.write("WAVEfmt ", 8);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(SAMPLE_RATE, 24);
  header.writeUInt32LE(SAMPLE_RATE * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(pcm.byteLength, 40);
  return Buffer.concat([header, pcm]);
}

/** Codec adaptation for shared media processing and transcription fallback. */
export async function decodeAwadaVoice(
  bytes: Buffer,
  maxBytes: number,
): Promise<Buffer | undefined> {
  const silk = await import("silk-wasm");
  if (!silk.isSilk(bytes)) return undefined;
  if ((silk.getDuration(bytes) * SAMPLE_RATE * 2) / 1000 + 44 > maxBytes)
    throw new Error("Decoded voice exceeds the media limit");
  const decoded = await silk.decode(bytes, SAMPLE_RATE);
  if (decoded.data.byteLength + 44 > maxBytes)
    throw new Error("Decoded voice exceeds the media limit");
  return pcmToWav(decoded.data);
}

export async function encodeAwadaVoice(
  bytes: Buffer,
  maxBytes: number,
): Promise<{ base64: string; duration: number }> {
  const silk = await import("silk-wasm");
  if (silk.isSilk(bytes))
    return {
      base64: bytes.toString("base64"),
      duration: Math.ceil(silk.getDuration(bytes) / 1000),
    };
  const dir = await mkdtemp(join(resolvePreferredOpenClawTmpDir(), "awada-voice-"));
  try {
    const input = join(dir, "source.audio");
    const output = join(dir, "voice.pcm");
    await writeFile(input, bytes, { mode: 0o600 });
    const { runFfmpeg } = await import("openclaw/plugin-sdk/media-runtime");
    await runFfmpeg(
      [
        "-v",
        "error",
        "-y",
        "-i",
        input,
        "-f",
        "s16le",
        "-ac",
        "1",
        "-ar",
        String(SAMPLE_RATE),
        "-fs",
        String(maxBytes + 1),
        output,
      ],
      { timeoutMs: 30_000 },
    );
    if ((await stat(output)).size > maxBytes)
      throw new Error("Voice conversion exceeds the media limit");
    const result = await silk.encode(await readFile(output), SAMPLE_RATE);
    if (result.data.byteLength > maxBytes) throw new Error("Encoded voice exceeds the media limit");
    return {
      base64: Buffer.from(result.data).toString("base64"),
      duration: Math.ceil(result.duration / 1000),
    };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
