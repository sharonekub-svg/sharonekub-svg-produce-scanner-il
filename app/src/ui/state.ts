// Tiny in-memory hand-off between the camera and result routes (avoids passing large JSON in URLs).
import type { ScanOutput } from '../model/engine';

let last: { output: ScanOutput; photoUri: string } | null = null;
export const setLastScan = (v: typeof last) => { last = v; };
export const getLastScan = () => last;

// Set when the user asks for "another angle" after an unsure result; consumed by the next scan.
let pendingPrevious: ScanOutput | null = null;
export const setPendingPrevious = (v: ScanOutput | null) => { pendingPrevious = v; };
export const takePendingPrevious = () => { const v = pendingPrevious; pendingPrevious = null; return v; };
export const peekPendingPrevious = () => pendingPrevious;
