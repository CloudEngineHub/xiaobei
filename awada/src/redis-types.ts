/** Awada v2 public envelopes. Redis is owned by Relay, never accessed by this plugin. */
export type InboundEventType = "MESSAGE_NEW" | "PROVIDER_EVENT" | "OPERATION_RESULT";
export type OutboundEventType = "REPLY_MESSAGE" | "COMMAND_EXECUTE";
export interface TextObject {
  type: "text";
  text: string;
}
export interface MediaObject {
  type: "image" | "file" | "audio" | "video";
  file_name?: string;
  file_url?: string;
  file_id?: string;
  base64?: string;
  duration?: number;
  provider_data?: Record<string, unknown>;
}
export type ImageObject = MediaObject & { type: "image" };
export type AudioObject = MediaObject & { type: "audio" };
export type FileObject = MediaObject & { type: "file" };
export interface ProviderContent {
  type: "provider";
  provider_type: string;
  data: unknown;
}
export type ContentObject = TextObject | MediaObject | ProviderContent;
export type Payload = ContentObject[];
export interface InboundMeta {
  platform: string;
  tenant_id: string;
  channel_id: string;
  lane: string;
  actor_type: string;
  user_id_external: string;
  session_id?: string;
  session_seq?: number;
  source_message_id?: string;
  conversation_id?: string;
  provider_account_id?: string;
  provider_event?: string;
  provider_raw?: Record<string, unknown>;
  operation_id?: string;
  sender_name?: string;
  channel_name?: string;
  identity_kind?: string;
  at_me?: boolean;
  room_type?: string | number;
  [key: string]: unknown;
}
export interface InboundEvent {
  schema_version: number;
  event_id: string;
  type: InboundEventType;
  timestamp: number;
  correlation_id?: string;
  trace_id?: string;
  meta: InboundMeta;
  payload: Payload;
}
export interface OutboundTarget {
  platform?: string;
  tenant_id: string;
  lane: string;
  user_id_external: string;
  channel_id: string;
  reply_token?: string;
  conversation_id?: string;
  action_ask?: [number, string[]];
}
export interface OutboundMeta {
  platform?: string;
  channel_id: string;
  user_id_external: string;
  tenant_id?: string;
  session_id?: string;
  source_event_id?: string;
  action_ask?: [number, string[]];
}
