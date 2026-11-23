<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import * as pdfjsLib from 'pdfjs-dist';
	import { TextLayer } from 'pdfjs-dist';
	import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
	import { auth } from '$lib/stores/auth.js';

	pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

	interface Props { src: string; highlight?: string; ondownload?: () => void; }
	let { src, highlight = '', ondownload }: Props = $props();
	let viewport = $state<HTMLDivElement>();
	let canvasContainer = $state<HTMLDivElement>();
	let loading = $state(true);
	let error = $state('');
	let pageCount = $state(0);
	let matchCount = $state(0);
	let highlightActive = $state(true);
	let zoom = $state(1);
	let pdf: pdfjsLib.PDFDocumentProxy | undefined;
	let resizeObserver: ResizeObserver | undefined;
	let renderVersion = 0;
	let lastRenderedWidth = 0;
	let activeRenderWidth = 0;
	let renderTimer: ReturnType<typeof setTimeout> | undefined;

	function highlightMatches(layer: HTMLElement, query: string) {
		if (!query.trim()) return 0;
		const words = query.trim().toLowerCase().split(/\s+/);
		let count = 0;
		for (const span of layer.querySelectorAll('span')) {
			if (words.some((word) => (span.textContent?.toLowerCase() ?? '').includes(word))) {
				span.classList.add('highlight'); count++;
			}
		}
		return count;
	}


	function scheduleRender(force = false) {
		if (!viewport || !pdf) return;
		const width = Math.floor(viewport.clientWidth);
		if (!width || (!force && (width === lastRenderedWidth || width === activeRenderWidth))) return;
		if (renderTimer !== undefined) clearTimeout(renderTimer);
		renderTimer = setTimeout(() => {
			renderTimer = undefined;
			void renderPages(width);
		}, 0);
	}

	async function renderPages(width: number) {
		if (!pdf || !canvasContainer || !width) return;
		const version = ++renderVersion;
		activeRenderWidth = width;
		canvasContainer.replaceChildren();
		const dpr = window.devicePixelRatio || 1;
		let nextMatchCount = 0;

		for (let number = 1; number <= pdf.numPages; number++) {
			const page = await pdf.getPage(number);
			if (version !== renderVersion) return;
			const base = page.getViewport({ scale: 1 });
			const pageViewport = page.getViewport({ scale: (width / base.width) * zoom });
			const pageDiv = document.createElement('div');
			pageDiv.className = 'pdf-page shadow-sm';
			pageDiv.style.width = `${Math.floor(pageViewport.width)}px`;
			pageDiv.style.height = `${Math.floor(pageViewport.height)}px`;
			const canvas = document.createElement('canvas');
			canvas.width = Math.floor(pageViewport.width * dpr);
			canvas.height = Math.floor(pageViewport.height * dpr);
			canvas.style.width = `${Math.floor(pageViewport.width)}px`;
			canvas.style.height = `${Math.floor(pageViewport.height)}px`;
			pageDiv.appendChild(canvas);
			const layer = document.createElement('div');
			layer.className = 'textLayer';
			pageDiv.appendChild(layer);
			canvasContainer.appendChild(pageDiv);
			const context = canvas.getContext('2d')!;
			context.scale(dpr, dpr);
			await page.render({ canvas, canvasContext: context, viewport: pageViewport }).promise;
			if (version !== renderVersion) return;
			await new TextLayer({ textContentSource: await page.getTextContent(), container: layer, viewport: pageViewport }).render();
			if (version !== renderVersion) return;
			if (highlightActive) nextMatchCount += highlightMatches(layer, highlight);
		}

		if (version !== renderVersion) return;
		matchCount = nextMatchCount;
		lastRenderedWidth = width;
		activeRenderWidth = 0;
		loading = false;
	}

	function setZoom(value: number) { zoom = value; scheduleRender(true); }
	function clearHighlights() { highlightActive = false; scheduleRender(true); }

	onMount(() => {
		(async () => {
			try {
				const state = get(auth);
				const httpHeaders: Record<string, string> = {};
				if (state.accessToken) httpHeaders.Authorization = `Bearer ${state.accessToken}`;
				pdf = await pdfjsLib.getDocument({ url: src, httpHeaders }).promise;
				pageCount = pdf.numPages;
				scheduleRender(true);
				resizeObserver = new ResizeObserver(() => scheduleRender());
				resizeObserver.observe(viewport!);
			} catch (e) { error = e instanceof Error ? e.message : 'Failed to load PDF'; loading = false; }
		})();
		return () => {
			renderVersion++;
			if (renderTimer !== undefined) clearTimeout(renderTimer);
			resizeObserver?.disconnect();
			pdf?.destroy();
		};
	});
</script>

<div class="flex flex-col h-full min-h-0 bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden">
	<div class="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-500 dark:text-gray-400">
		{#if pageCount > 0}<span class="inline-flex items-center"><span class="i-lucide-file-text mr-1"></span>{pageCount} {pageCount === 1 ? 'page' : 'pages'}</span>{/if}
		<label class="inline-flex items-center gap-2 ml-auto"><span>{Math.round(zoom * 100)}%</span><input aria-label="Zoom PDF" type="range" min="0.75" max="2" step="0.25" value={zoom} onchange={(event) => setZoom(Number(event.currentTarget.value))} /></label>
		<button class="btn-ghost btn-sm" onclick={() => setZoom(1)}>Fit width</button>
		<a class="btn-ghost btn-sm no-underline" href={src} target="_blank" rel="noopener noreferrer">Open PDF</a>
		{#if ondownload}<button class="btn-ghost btn-sm" onclick={ondownload}>Download PDF</button>{/if}
		{#if highlightActive && matchCount > 0}<span class="text-amber-600 dark:text-amber-400">{matchCount} {matchCount === 1 ? 'match' : 'matches'}</span><button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" title="Clear highlights" onclick={clearHighlights}><span class="i-lucide-x text-sm"></span></button>{/if}
	</div>
	{#if error}
		<div class="flex-1 flex items-center justify-center p-4 text-center"><span class="i-lucide-alert-circle text-red-400 mr-2"></span><span class="text-gray-600 dark:text-gray-400">{error}</span></div>
	{:else}
		<div bind:this={viewport} class="flex-1 min-h-0 min-w-0 overflow-x-auto overflow-y-scroll overscroll-contain p-3" style="scrollbar-gutter: stable;">
			{#if loading}<div class="flex items-center justify-center h-full"><span class="i-lucide-loader-2 text-2xl text-gray-400 animate-spin"></span></div>{/if}
			<div bind:this={canvasContainer} class="flex min-w-max flex-col items-center gap-3"></div>
		</div>
	{/if}
</div>

<style>
	:global(.pdf-page) { position: relative; flex: none; }
	:global(.textLayer) { position: absolute; inset: 0; overflow: clip; line-height: 1; z-index: 1; }
	:global(.textLayer span) { color: transparent; position: absolute; white-space: pre; cursor: text; transform-origin: 0 0; }
	:global(.textLayer ::selection) { background: rgba(0, 0, 255, 0.25); }
	:global(.textLayer .highlight) { background: rgba(251, 191, 36, 0.4); border-radius: 2px; }
</style>
