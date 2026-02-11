<script lang="ts">
	import { onMount } from 'svelte';
	import * as pdfjsLib from 'pdfjs-dist';
	import { TextLayer } from 'pdfjs-dist';
	import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

	pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

	interface Props { src: string; }
	let { src }: Props = $props();

	let canvasContainer: HTMLDivElement;
	let loading = $state(true);
	let error = $state('');
	let pageCount = $state(0);

	onMount(() => {
		let pdf: pdfjsLib.PDFDocumentProxy | undefined;

		(async () => {
			try {
				pdf = await pdfjsLib.getDocument(src).promise;
				pageCount = pdf.numPages;
				loading = false;

				const containerWidth = canvasContainer.clientWidth;
				const dpr = window.devicePixelRatio || 1;

				for (let i = 1; i <= pdf.numPages; i++) {
					const page = await pdf.getPage(i);
					const unscaledViewport = page.getViewport({ scale: 1 });
					const scale = containerWidth / unscaledViewport.width;
					const viewport = page.getViewport({ scale });

					// Page wrapper (positions text layer over canvas)
					const pageDiv = document.createElement('div');
					pageDiv.style.position = 'relative';
					pageDiv.style.width = `${Math.floor(viewport.width)}px`;
					pageDiv.style.height = `${Math.floor(viewport.height)}px`;
					pageDiv.className = 'shadow-sm';

					// Canvas for rendering
					const canvas = document.createElement('canvas');
					canvas.width = Math.floor(viewport.width * dpr);
					canvas.height = Math.floor(viewport.height * dpr);
					canvas.style.width = `${Math.floor(viewport.width)}px`;
					canvas.style.height = `${Math.floor(viewport.height)}px`;
					canvas.style.display = 'block';
					pageDiv.appendChild(canvas);

					// Text layer for selection
					const textLayerDiv = document.createElement('div');
					textLayerDiv.className = 'textLayer';
					pageDiv.appendChild(textLayerDiv);

					canvasContainer.appendChild(pageDiv);

					// Render canvas
					const ctx = canvas.getContext('2d')!;
					ctx.scale(dpr, dpr);
					await page.render({ canvas, canvasContext: ctx, viewport }).promise;

					// Render text layer
					const textContent = await page.getTextContent();
					const textLayer = new TextLayer({
						textContentSource: textContent,
						container: textLayerDiv,
						viewport,
					});
					await textLayer.render();
				}
			} catch (e) {
				error = e instanceof Error ? e.message : 'Failed to load PDF';
				loading = false;
			}
		})();

		return () => {
			pdf?.destroy();
		};
	});
</script>

<div class="flex flex-col h-full bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden">
	{#if error}
		<div class="flex-1 flex items-center justify-center">
			<span class="i-lucide-alert-circle text-red-400 mr-2"></span>
			<span class="text-gray-600 dark:text-gray-400">{error}</span>
		</div>
	{:else}
		{#if pageCount > 0}
			<div class="flex items-center px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-500 dark:text-gray-400">
				<span class="i-lucide-file-text mr-1"></span>
				{pageCount} {pageCount === 1 ? 'page' : 'pages'}
			</div>
		{/if}
		<div class="flex-1 overflow-y-auto p-4">
			{#if loading}
				<div class="flex items-center justify-center h-full">
					<span class="i-lucide-loader-2 text-2xl text-gray-400 animate-spin"></span>
				</div>
			{/if}
			<div bind:this={canvasContainer} class="flex flex-col items-center gap-2"></div>
		</div>
	{/if}
</div>

<style>
	/* PDF.js text layer styles — enables text selection over rendered canvases */
	:global(.textLayer) {
		position: absolute;
		text-align: initial;
		inset: 0;
		overflow: clip;
		opacity: 1;
		line-height: 1;
		-webkit-text-size-adjust: none;
		-moz-text-size-adjust: none;
		text-size-adjust: none;
		forced-color-adjust: none;
		transform-origin: 0 0;
		caret-color: CanvasText;
		z-index: 0;
	}

	:global(.textLayer) {
		--min-font-size: 1;
		--text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size));
		--min-font-size-inv: calc(1 / var(--min-font-size));
	}

	:global(.textLayer :is(span, br)) {
		color: transparent;
		position: absolute;
		white-space: pre;
		cursor: text;
		transform-origin: 0% 0%;
	}

	:global(.textLayer > :not(.markedContent)),
	:global(.textLayer .markedContent span:not(.markedContent)) {
		z-index: 1;
		--font-height: 0;
		font-size: calc(var(--text-scale-factor) * var(--font-height));
		--scale-x: 1;
		--rotate: 0deg;
		transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv));
	}

	:global(.textLayer .markedContent) {
		display: contents;
	}

	:global(.textLayer span[role="img"]) {
		-webkit-user-select: none;
		-moz-user-select: none;
		user-select: none;
		cursor: default;
	}

	:global(.textLayer ::-moz-selection) {
		background: rgba(0, 0, 255, 0.25);
	}

	:global(.textLayer ::selection) {
		background: rgba(0, 0, 255, 0.25);
	}

	:global(.textLayer br::-moz-selection) {
		background: transparent;
	}

	:global(.textLayer br::selection) {
		background: transparent;
	}

	:global(.textLayer .endOfContent) {
		display: block;
		position: absolute;
		inset: 100% 0 0;
		z-index: 0;
		cursor: default;
		-webkit-user-select: none;
		-moz-user-select: none;
		user-select: none;
	}

	:global(.textLayer.selecting .endOfContent) {
		top: 0;
	}
</style>
