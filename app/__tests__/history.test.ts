import { beforeEach, describe, expect, it, jest } from '@jest/globals';

// In-memory stand-ins for the device file system and image resizer.
const mockFiles = new Map<string, string>();
jest.mock('expo-file-system', () => {
  const join = (...p: any[]) => p.map((x) => (typeof x === 'string' ? x : x.uri)).join('/');
  class Directory { uri: string; constructor(...p: any[]) { this.uri = join(...p); } get exists() { return true; } create() {} }
  class File {
    uri: string;
    constructor(...p: any[]) { this.uri = join(...p); }
    get exists() { return mockFiles.has(this.uri); }
    textSync() { return mockFiles.get(this.uri)!; }
    write(s: string) { mockFiles.set(this.uri, s); }
    delete() { mockFiles.delete(this.uri); }
    async copy(dest: File) { mockFiles.set(dest.uri, 'jpg'); }
  }
  return { Directory, File, Paths: { document: { uri: 'doc' } } };
});
jest.mock('expo-image-manipulator', () => ({
  SaveFormat: { JPEG: 'jpeg' },
  ImageManipulator: { manipulate: () => ({ resize: () => ({ renderAsync: async () => ({ saveAsync: async () => ({ uri: 'cache/t.jpg' }) }) }) }) },
}));

// Account: signed in or not, and an in-memory cloud table.
let mockSignedIn = false;
const mockCloud: { t: number; result: any; thumb: string | null }[] = [];
jest.mock('../src/auth', () => ({ getSession: () => (mockSignedIn ? { name: 'x' } : null) }));
jest.mock('../src/cloud', () => ({
  cloudList: async () => [...mockCloud].sort((a, b) => b.t - a.t),
  cloudAdd: async (rows: any[]) => { mockCloud.push(...rows); return true; },
  cloudRemove: async (t: number) => { mockCloud.splice(0, mockCloud.length, ...mockCloud.filter((r) => r.t !== t)); return true; },
  cloudClear: async () => { mockCloud.length = 0; return true; },
}));

const out = (status: string, score: number | null = 8) =>
  ({ result: { status, score, produce: 'apple', produce_he: 'תפוח', emoji: '🍎' }, top3: [], angles: 1 }) as any;

function freshModule() {
  let m!: typeof import('../src/history');
  jest.isolateModules(() => { m = require('../src/history'); });
  return m;
}

describe('my scans history', () => {
  beforeEach(() => { mockFiles.clear(); mockCloud.length = 0; mockSignedIn = false; });

  it('keeps only successful scans, newest first, with a thumbnail', async () => {
    const h = freshModule();
    await h.addToHistory('p1.jpg', out('ok', 9));
    await h.addToHistory('p2.jpg', out('unsure'));
    await new Promise((r) => setTimeout(r, 2));
    await h.addToHistory('p3.jpg', out('ok', 2));
    const list = h.loadHistory();
    expect(list.map((e) => e.output.result.score)).toEqual([2, 9]);
    expect(list[0].thumb).toMatch(/^doc\/history\/\d+\.jpg$/);
    expect(h.summarize(list)).toEqual({ total: 2, scored: 2, good: 1, bad: 1 });
  });

  it('persists across app restarts and deletes thumbnails with their entries', async () => {
    const h = freshModule();
    await h.addToHistory('p.jpg', out('ok'));
    const [e] = h.loadHistory();
    const again = freshModule(); // new module instance = app restart
    expect(again.loadHistory().map((x) => x.id)).toEqual([e.id]);
    again.removeFromHistory(e.id);
    expect(again.loadHistory()).toEqual([]);
    expect(mockFiles.has(e.thumb!)).toBe(false);
  });

  it('caps the list at HMAX and clears everything', async () => {
    const h = freshModule();
    for (let i = 0; i < h.HMAX + 3; i++) { await h.addToHistory('p.jpg', out('ok')); await new Promise((r) => setTimeout(r, 1)); }
    expect(h.loadHistory()).toHaveLength(h.HMAX);
    h.clearHistory();
    expect(h.loadHistory()).toEqual([]);
    expect([...mockFiles.keys()].filter((k) => k.endsWith('.jpg'))).toEqual([]);
  });

  it('signed in: new scans go to the account, and sync merges both ways (same row shape as the web)', async () => {
    mockSignedIn = true;
    mockFiles.set('doc/history/seed.jpg', 'x');
    mockCloud.push({ t: 5, result: { status: 'ok', score: 3, produce: 'banana', produce_he: 'בננה', top3: [{ produce: 'banana', he: 'בננה', prob: 0.9 }] },
                     thumb: 'data:image/jpeg;base64,QUJD' });
    const h = freshModule();
    await h.addToHistory('p.jpg', out('ok', 9));
    await new Promise((r) => setTimeout(r, 5));
    expect(mockCloud.map((r) => r.t)).toContain(h.loadHistory()[0].id);
    expect(mockCloud.find((r) => r.t !== 5)!.result.top3).toEqual([]);
    await h.syncHistory();
    const list = h.loadHistory();
    const web = list.find((e) => e.id === 5)!;
    expect(web.output.result.produce).toBe('banana');
    expect(web.output.top3).toHaveLength(1);
    expect((web.output.result as any).top3).toBeUndefined();
    expect(web.thumb).toBe('doc/history/5.jpg');
    h.removeFromHistory(5);
    await new Promise((r) => setTimeout(r, 1));
    expect(mockCloud.map((r) => r.t)).not.toContain(5);
  });

  it('signed out: nothing is sent to the account', async () => {
    const h = freshModule();
    await h.addToHistory('p.jpg', out('ok'));
    await h.syncHistory();
    expect(mockCloud).toEqual([]);
  });
});
