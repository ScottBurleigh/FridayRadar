import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { School } from "./types";

export const ZIP_RADIUS_MILES = 25;
const EARTH_MILES = 3958.8;

type ZipMap = Record<string, [number, number]>;

let zipCache: ZipMap | null = null;

export function loadZipCentroids(): ZipMap {
  if (zipCache) return zipCache;
  const path = join(process.cwd(), "data", "zip-centroids.json");
  zipCache = JSON.parse(readFileSync(path, "utf8")) as ZipMap;
  return zipCache;
}

export function padZip(zip: string | number | null | undefined): string | null {
  if (zip == null) return null;
  const digits = String(zip).replace(/\D/g, "");
  if (digits.length < 5) return digits.padStart(5, "0");
  return digits.slice(0, 5);
}

export function haversineMiles(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_MILES * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function coordsForZip(zip: string): { lat: number; lng: number } | null {
  const padded = padZip(zip);
  if (!padded) return null;
  const pair = loadZipCentroids()[padded];
  if (!pair) return null;
  return { lat: pair[0], lng: pair[1] };
}

export function schoolCoords(
  school: School,
): { lat: number; lng: number } | null {
  if (school.lat != null && school.lng != null) {
    return { lat: school.lat, lng: school.lng };
  }
  if (school.zip) return coordsForZip(school.zip);
  return null;
}

export function schoolWithinZipRadius(school: School, zip: string, miles = ZIP_RADIUS_MILES): boolean {
  const origin = coordsForZip(zip);
  const dest = schoolCoords(school);
  if (!origin || !dest) return false;
  return haversineMiles(origin.lat, origin.lng, dest.lat, dest.lng) <= miles;
}
