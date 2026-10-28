// XENO ECOSYSTEM — the experimental bodies. The build lives in bodyset.ts (assembly), ncb.ts (the non-central body's nodes), observer.ts (the observation node), probes.ts, cables.ts,
// hardware.ts and weathering.ts; the mapping from a record to what the bodies do lives in bodyState.ts. This module keeps the names the view and the tests import.
export { buildBodies, studioEnvironment, NCB_AT, OBSERVER_AT, type BodySet } from './bodyset';
export { bodyState, FLASH_TICKS, type BodyState } from './bodyState';
export { perforated } from './geom';
export type { PartInfo } from './ncb';
