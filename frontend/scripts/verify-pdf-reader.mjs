import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('..', import.meta.url);
const route = await readFile(new URL('src/routes/documents/[id]/+page.svelte', root), 'utf8');
const viewer = await readFile(new URL('src/lib/components/documents/PdfPreview.svelte', root), 'utf8');

assert.match(route, /document-viewer/);
assert.match(route, /order-1 md:order-2/);
assert.match(route, /order-2 md:order-1/);
assert.match(viewer, /aria-label="Zoom PDF"/);
assert.match(viewer, /Fit width/);
assert.match(viewer, /Open PDF/);
assert.match(viewer, /Download PDF/);
assert.match(viewer, /ResizeObserver\(\(\) => scheduleRender\(\)\)/);
assert.match(viewer, /resizeObserver\.observe\(viewport!/);
assert.doesNotMatch(viewer, /resizeObserver\.observe\(canvasContainer/);
assert.match(viewer, /width === lastRenderedWidth/);
assert.match(viewer, /renderVersion = 0/);
assert.match(viewer, /renderVersion\+\+/);
assert.match(viewer, /min-w-0 overflow-x-auto overflow-y-scroll/);

console.log('PDF reader stable-render responsive contract verified');
