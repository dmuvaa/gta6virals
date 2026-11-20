export type Me = {
  id: string; email: string; name: string; plan: string; plan_status: string; has_billing: boolean;
  limits: { name: string; price: number; hours: number; exports: number; captions: boolean; watermark: boolean; max_video_hours: number };
  usage: { hours: number; exports: number };
};
export type ProjectSummary = {
  id: string; url: string; title: string; platform: string; uploader: string; thumbnail: string | null;
  duration: number; stage: string; progress: number; message: string; error: string | null; created_at: string;
  window: [number, number]; counts: { moments: number; kept: number; ready: number };
};
export type Moment = {
  id: string; rank: number; score: number; reason: string; label: string; source_start: number; source_end: number;
  state: "new" | "kept" | "discarded"; status: string; flag: "static" | "camera" | null; format: string | null;
  captioned: boolean; error: string | null; start: number; end: number; peak: number;
  file_url?: string; download_url?: string; thumb_url?: string;
};
export type Project = Omit<ProjectSummary, "counts"> & {
  timeline: number[]; notes: string[]; watermark: boolean;
  settings: { format: string; captions: boolean; facecam_corner: string; clip_len: number };
  facecam: { rect?: { x: number; y: number; w: number; h: number }; source?: string };
  moments: Moment[];
};
