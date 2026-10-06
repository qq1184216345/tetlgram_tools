/** 桌面端本地会话轻量加密存储（提高随手篡改门槛，非绝对防破解） */

const PREFIX = "pwenc:v1:";
const APP_MATERIAL = "paperwing·纸翼·license·v1";

function toB64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]!);
  return btoa(s);
}

function fromB64(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveKey(): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey("raw", enc.encode(APP_MATERIAL), "PBKDF2", false, [
    "deriveKey",
  ]);
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: enc.encode("paperwing-desktop-salt"),
      iterations: 120_000,
      hash: "SHA-256",
    },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function secureSet(key: string, value: string): Promise<void> {
  if (!value) {
    localStorage.removeItem(key);
    return;
  }
  try {
    const cryptoKey = await deriveKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const cipher = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      cryptoKey,
      new TextEncoder().encode(value),
    );
    const packed = `${PREFIX}${toB64(iv.buffer)}:${toB64(cipher)}`;
    localStorage.setItem(key, packed);
  } catch {
    localStorage.setItem(key, value);
  }
}

export async function secureGet(key: string): Promise<string | null> {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  if (!raw.startsWith(PREFIX)) return raw;
  try {
    const body = raw.slice(PREFIX.length);
    const [ivB64, ctB64] = body.split(":");
    if (!ivB64 || !ctB64) return null;
    const cryptoKey = await deriveKey();
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromB64(ivB64) },
      cryptoKey,
      fromB64(ctB64),
    );
    return new TextDecoder().decode(plain);
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

export function secureRemove(key: string): void {
  localStorage.removeItem(key);
}
