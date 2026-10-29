export type Job = {
  id: string;
  lab: number;
  action: string;
  status: string;
  message: string;
  created_at: string;
  error: string | null;
  result: any;
};
export const active = (job?: Job) =>
  !!job && ["queued", "running", "cancelling"].includes(job.status);
export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined
          ? {}
          : { "Content-Type": "application/json", "X-Eyazis": "local" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      let error;
      try {
        error = await response.json();
      } catch {
        error = { detail: response.statusText };
      }
      throw new Error(
        typeof error.detail === "string"
          ? error.detail
          : JSON.stringify(error.detail),
      );
    }
    return response.json();
  } finally {
    clearTimeout(timer);
  }
}
export async function upload(file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/uploads", {
    method: "POST",
    headers: { "X-Eyazis": "local" },
    body: form,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Не удалось загрузить файл");
  return data as { id: string; name: string; bytes: number; url: string };
}
export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
