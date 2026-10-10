import { STATIC_DEMO } from "./demo-mode";

/** Illustrative map coordinates near Tirana, never observed crash locations. */
export const DEMO_CITY_KEY = "tirana";
export const DEMO_CITY_NAME = "Tirana";
export const DEMO_CENTER: [number, number] = [19.8187, 41.3275];
export function demoLongitude(value: number): number {
  return STATIC_DEMO ? Number((DEMO_CENTER[0] + (value - 16.869) * 0.5).toFixed(6)) : value;
}
export function demoLatitude(value: number): number {
  return STATIC_DEMO ? Number((DEMO_CENTER[1] + (value - 41.126) * 0.5).toFixed(6)) : value;
}
export function demoCenter(fallback: [number, number]): [number, number] {
  return STATIC_DEMO ? DEMO_CENTER : fallback;
}
