/** 简单 semver 比较：a>b → 1，a<b → -1，相等 → 0 */

function parseParts(version: string): number[] {
  return String(version || "")
    .trim()
    .replace(/^[vV]/, "")
    .split(/[.+_-]/)
    .map((p) => {
      const n = parseInt(p.replace(/[^0-9].*$/, ""), 10);
      return Number.isFinite(n) ? n : 0;
    });
}

export function compareVersions(a: string, b: string): number {
  const pa = parseParts(a);
  const pb = parseParts(b);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const x = pa[i] ?? 0;
    const y = pb[i] ?? 0;
    if (x > y) return 1;
    if (x < y) return -1;
  }
  return 0;
}

export function isNewerVersion(remote: string, local: string): boolean {
  return compareVersions(remote, local) > 0;
}

export type AppVersionManifest = {
  version: string;
  url?: string;
  download_url?: string;
  notes?: string;
  force?: boolean;
  force_update?: boolean;
};

export function manifestDownloadUrl(m: AppVersionManifest): string {
  return (m.download_url || m.url || "").trim();
}

export function manifestForce(m: AppVersionManifest): boolean {
  return Boolean(m.force_update || m.force);
}
