const FNV_OFFSET = 0x811c9dc5;
const FNV_PRIME = 0x01000193;
const HUES = 360;

/** A stable hue per speaker. Same FNV-1a hash as orgestra.personas.persona_hue on the server. */
export function personaHue(slug: string): number {
  let value = FNV_OFFSET;
  for (const byte of new TextEncoder().encode(slug)) {
    value = Math.imul(value ^ byte, FNV_PRIME) >>> 0;
  }
  return value % HUES;
}
