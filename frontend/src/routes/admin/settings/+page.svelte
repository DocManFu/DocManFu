<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { isAdmin } from '$lib/stores/auth.js';
	import { toasts } from '$lib/stores/toast.js';
	import {
		getAISettings,
		updateAISettings,
		testAIConnection,
		resetAISettings,
	} from '$lib/api/settings.js';
	import type { AISettings, AISettingValue } from '$lib/types/index.js';

	// --- Model catalogs ---

	interface ModelInfo {
		id: string;
		name: string;
		description: string;
		cost: string;
	}

	const OPENAI_MODELS: ModelInfo[] = [
		{
			id: 'gpt-4o-mini',
			name: 'GPT-4o Mini',
			description: 'Fast and affordable. Good for most document analysis.',
			cost: 'Estimated ~$0.001 per document (fraction of a cent)',
		},
		{
			id: 'gpt-4o',
			name: 'GPT-4o',
			description: 'Most capable multimodal model. Best accuracy for complex documents.',
			cost: 'Estimated ~$0.01 per document (~1 cent)',
		},
		{
			id: 'gpt-4.1-mini',
			name: 'GPT-4.1 Mini',
			description: 'Latest generation small model. Fast with improved accuracy.',
			cost: 'Estimated ~$0.0015 per document (fraction of a cent)',
		},
		{
			id: 'gpt-4.1',
			name: 'GPT-4.1',
			description: 'Latest generation flagship. Best coding and instruction following.',
			cost: 'Estimated ~$0.008 per document (~1 cent)',
		},
	];

	const ANTHROPIC_MODELS: ModelInfo[] = [
		{
			id: 'claude-sonnet-4-5-20250929',
			name: 'Claude Sonnet 4.5',
			description: 'Best balance of speed, accuracy, and cost. Recommended for most use cases.',
			cost: 'Estimated ~$0.01 per document (~1 cent)',
		},
		{
			id: 'claude-haiku-4-5-20251001',
			name: 'Claude Haiku 4.5',
			description: 'Fastest and most affordable. Good for straightforward documents.',
			cost: 'Estimated ~$0.003 per document (fraction of a cent)',
		},
		{
			id: 'claude-opus-4-6',
			name: 'Claude Opus 4.6',
			description: 'Most capable model. Best for complex or ambiguous documents.',
			cost: 'Estimated ~$0.06 per document (~6 cents)',
		},
	];

	let loading = $state(true);
	let saving = $state(false);
	let testing = $state(false);
	let resetting = $state(false);
	let showAdvanced = $state(false);
	let useCustomModel = $state(false);

	let settings = $state<AISettings>({});
	let testResult = $state<{ success: boolean; message: string } | null>(null);

	// Form values
	let provider = $state('none');
	let apiKey = $state('');
	let model = $state('');
	let baseUrl = $state('');
	let maxTextLength = $state(4000);
	let timeout = $state(60);
	let maxPages = $state(5);
	let visionDpi = $state(150);
	let visionModel = $state('');

	let providerModels = $derived(
		provider === 'openai' ? OPENAI_MODELS : provider === 'anthropic' ? ANTHROPIC_MODELS : [],
	);

	let selectedModelInfo = $derived(providerModels.find((m) => m.id === model));

	// Check if current model is in the catalog
	$effect(() => {
		if (provider === 'openai' || provider === 'anthropic') {
			const inCatalog = providerModels.some((m) => m.id === model);
			useCustomModel = model !== '' && !inCatalog;
		}
	});

	onMount(() => {
		if (!$isAdmin) {
			goto('/documents');
			return;
		}
		loadSettings();
	});

	function getVal(s: AISettings, key: string): string {
		const v = s[key];
		if (!v) return '';
		if (v.is_set) return v.value ?? '';
		return v.value ?? '';
	}

	function getSource(key: string): string {
		return settings[key]?.source ?? 'default';
	}

	async function loadSettings() {
		loading = true;
		try {
			settings = await getAISettings();
			provider = getVal(settings, 'ai_provider') || 'none';
			apiKey = settings['ai_api_key']?.is_set ? (settings['ai_api_key'].value ?? '') : '';
			model = getVal(settings, 'ai_model') || '';
			baseUrl = getVal(settings, 'ai_base_url') || '';
			maxTextLength = parseInt(getVal(settings, 'ai_max_text_length') || '4000') || 4000;
			timeout = parseInt(getVal(settings, 'ai_timeout') || '60') || 60;
			maxPages = parseInt(getVal(settings, 'ai_max_pages') || '5') || 5;
			visionDpi = parseInt(getVal(settings, 'ai_vision_dpi') || '150') || 150;
			visionModel = getVal(settings, 'ai_vision_model') || '';
		} catch (err) {
			toasts.error('Failed to load AI settings');
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		saving = true;
		testResult = null;
		try {
			const data: Record<string, unknown> = {
				ai_provider: provider,
				ai_model: model,
				ai_base_url: baseUrl,
				ai_max_text_length: maxTextLength,
				ai_timeout: timeout,
				ai_max_pages: maxPages,
				ai_vision_dpi: visionDpi,
				ai_vision_model: visionModel,
			};
			// Only send API key if it was changed (not the masked placeholder)
			if (apiKey && !apiKey.startsWith('****')) {
				data.ai_api_key = apiKey;
			}
			settings = await updateAISettings(data);
			// Refresh form from saved values
			provider = getVal(settings, 'ai_provider') || 'none';
			apiKey = settings['ai_api_key']?.is_set ? (settings['ai_api_key'].value ?? '') : '';
			model = getVal(settings, 'ai_model') || '';
			baseUrl = getVal(settings, 'ai_base_url') || '';
			toasts.success('AI settings saved');
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to save settings');
		} finally {
			saving = false;
		}
	}

	async function handleTest() {
		testing = true;
		testResult = null;
		try {
			const data: Record<string, unknown> = {
				ai_provider: provider,
				ai_model: model,
				ai_base_url: baseUrl,
				ai_timeout: timeout,
			};
			if (apiKey && !apiKey.startsWith('****')) {
				data.ai_api_key = apiKey;
			}
			const result = await testAIConnection(data);
			testResult = { success: result.success, message: result.message };
		} catch (err) {
			testResult = {
				success: false,
				message: err instanceof Error ? err.message : 'Connection test failed',
			};
		} finally {
			testing = false;
		}
	}

	async function handleReset() {
		resetting = true;
		testResult = null;
		try {
			await resetAISettings();
			toasts.success('AI settings reset to defaults');
			await loadSettings();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to reset settings');
		} finally {
			resetting = false;
		}
	}

	function handleModelSelect(e: Event) {
		const value = (e.target as HTMLSelectElement).value;
		if (value === '__custom__') {
			useCustomModel = true;
			model = '';
		} else {
			useCustomModel = false;
			model = value;
		}
	}

	let needsApiKey = $derived(provider === 'openai' || provider === 'anthropic');
	let needsBaseUrl = $derived(provider === 'ollama');
</script>

<svelte:head>
	<title>AI Settings - DocManFu</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<!-- Admin tabs -->
	<div class="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
		<a
			href="/admin/users"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
		>
			Users
		</a>
		<a
			href="/admin/settings"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-brand-500 text-brand-600 dark:text-brand-400"
		>
			Settings
		</a>
		<a
			href="/admin/import"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
		>
			Import
		</a>
		<a
			href="/admin/processing"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
		>
			Processing
		</a>
	</div>

	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">AI Settings</h1>
			<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
				Configure the AI provider used for document analysis.
			</p>
		</div>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div class="i-lucide-loader-2 animate-spin text-2xl text-gray-400"></div>
		</div>
	{:else}
		<!-- Test result banner -->
		{#if testResult}
			<div
				class="mb-6 p-4 rounded-lg border {testResult.success
					? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
					: 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'}"
			>
				<div class="flex items-center gap-2">
					{#if testResult.success}
						<span class="i-lucide-check-circle text-green-600 dark:text-green-400"></span>
						<span class="text-sm font-medium text-green-800 dark:text-green-300"
							>{testResult.message}</span
						>
					{:else}
						<span class="i-lucide-x-circle text-red-600 dark:text-red-400"></span>
						<span class="text-sm font-medium text-red-800 dark:text-red-300"
							>{testResult.message}</span
						>
					{/if}
					<button
						class="ml-auto text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
						onclick={() => (testResult = null)}
					>
						<span class="i-lucide-x text-sm"></span>
					</button>
				</div>
			</div>
		{/if}

		<div
			class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 space-y-6"
		>
			<!-- Provider -->
			<div>
				<div class="flex items-center gap-2 mb-1">
					<label for="provider" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
						AI Provider
					</label>
					{@render sourceBadge(getSource('ai_provider'))}
				</div>
				<select
					id="provider"
					bind:value={provider}
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
				>
					<option value="none">None (disabled)</option>
					<option value="openai">OpenAI</option>
					<option value="anthropic">Anthropic</option>
					<option value="ollama">Ollama (local)</option>
				</select>
			</div>

			{#if provider !== 'none'}
				<!-- Provider-specific setup instructions -->
				{#if provider === 'openai'}
					<div
						class="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-4 text-sm"
					>
						<h4 class="font-medium text-blue-900 dark:text-blue-200 mb-2 flex items-center gap-1.5">
							<span class="i-lucide-info text-blue-500"></span>
							Getting started with OpenAI
						</h4>
						<ol class="list-decimal list-inside space-y-1 text-blue-800 dark:text-blue-300">
							<li>
								Go to <a
									href="https://platform.openai.com/api-keys"
									target="_blank"
									rel="noopener"
									class="underline font-medium hover:text-blue-600 dark:hover:text-blue-100"
									>platform.openai.com/api-keys</a
								>
							</li>
							<li>Sign in or create an account</li>
							<li>Click "Create new secret key" and copy it</li>
							<li>
								Paste the key below (starts with <code
									class="bg-blue-100 dark:bg-blue-800 px-1 rounded text-xs">sk-</code
								>)
							</li>
						</ol>
						<p class="mt-2 text-xs text-blue-600 dark:text-blue-400">
							You'll need a payment method on your OpenAI account. See
							<a
								href="https://platform.openai.com/docs/pricing"
								target="_blank"
								rel="noopener"
								class="underline hover:text-blue-500 dark:hover:text-blue-200">pricing details</a
							>.
						</p>
					</div>
				{:else if provider === 'anthropic'}
					<div
						class="rounded-lg border border-purple-200 dark:border-purple-800 bg-purple-50 dark:bg-purple-900/20 p-4 text-sm"
					>
						<h4
							class="font-medium text-purple-900 dark:text-purple-200 mb-2 flex items-center gap-1.5"
						>
							<span class="i-lucide-info text-purple-500"></span>
							Getting started with Anthropic
						</h4>
						<ol class="list-decimal list-inside space-y-1 text-purple-800 dark:text-purple-300">
							<li>
								Go to <a
									href="https://console.anthropic.com/settings/keys"
									target="_blank"
									rel="noopener"
									class="underline font-medium hover:text-purple-600 dark:hover:text-purple-100"
									>console.anthropic.com/settings/keys</a
								>
							</li>
							<li>Sign in or create an account</li>
							<li>Click "Create Key" and copy it</li>
							<li>
								Paste the key below (starts with <code
									class="bg-purple-100 dark:bg-purple-800 px-1 rounded text-xs">sk-ant-</code
								>)
							</li>
						</ol>
						<p class="mt-2 text-xs text-purple-600 dark:text-purple-400">
							You'll need to add credits to your account. See
							<a
								href="https://docs.anthropic.com/en/docs/about-claude/models"
								target="_blank"
								rel="noopener"
								class="underline hover:text-purple-500 dark:hover:text-purple-200"
								>model details and pricing</a
							>.
						</p>
					</div>
				{/if}

				<!-- API Key (openai/anthropic only) -->
				{#if needsApiKey}
					<div>
						<div class="flex items-center gap-2 mb-1">
							<label
								for="api-key"
								class="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								API Key
							</label>
							{@render sourceBadge(getSource('ai_api_key'))}
						</div>
						<input
							id="api-key"
							type="password"
							bind:value={apiKey}
							placeholder={provider === 'openai' ? 'sk-...' : 'sk-ant-...'}
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							{#if apiKey.startsWith('****')}
								API key is set. Enter a new value to replace it.
							{:else}
								Your API key is encrypted before storage.
							{/if}
						</p>
					</div>
				{/if}

				<!-- Model selector (openai/anthropic) -->
				{#if provider === 'openai' || provider === 'anthropic'}
					<div>
						<div class="flex items-center gap-2 mb-1">
							<label
								for="model-select"
								class="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								Model
							</label>
							{@render sourceBadge(getSource('ai_model'))}
						</div>

						{#if !useCustomModel}
							<select
								id="model-select"
								value={model || providerModels[0]?.id || ''}
								onchange={handleModelSelect}
								class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
							>
								{#each providerModels as m}
									<option value={m.id}>{m.name}</option>
								{/each}
								<option value="__custom__">Custom model...</option>
							</select>

							<!-- Model info card -->
							{@const displayModel =
								selectedModelInfo ||
								providerModels.find((m) => m.id === (model || providerModels[0]?.id))}
							{#if displayModel}
								<div
									class="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-3"
								>
									<p class="text-sm text-gray-700 dark:text-gray-300">{displayModel.description}</p>
									<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
										<span class="i-lucide-coins text-xs mr-0.5 align-text-bottom"></span>
										{displayModel.cost}
									</p>
									<p class="text-[10px] text-gray-400 dark:text-gray-500 mt-1">
										Cost estimates are approximate and may be outdated. Check
										{#if provider === 'openai'}
											<a
												href="https://platform.openai.com/docs/pricing"
												target="_blank"
												rel="noopener"
												class="underline">OpenAI pricing</a
											>
										{:else}
											<a
												href="https://docs.anthropic.com/en/docs/about-claude/models"
												target="_blank"
												rel="noopener"
												class="underline">Anthropic pricing</a
											>
										{/if}
										for current rates.
									</p>
								</div>
							{/if}
						{:else}
							<div class="flex gap-2">
								<input
									id="model-custom"
									type="text"
									bind:value={model}
									placeholder="Enter model ID..."
									class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
								/>
								<button
									class="btn btn-secondary text-sm"
									onclick={() => {
										useCustomModel = false;
										model = providerModels[0]?.id || '';
									}}
								>
									Back to list
								</button>
							</div>
							<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
								{#if provider === 'openai'}
									See all available models at
									<a
										href="https://platform.openai.com/docs/models"
										target="_blank"
										rel="noopener"
										class="underline hover:text-gray-700 dark:hover:text-gray-300"
										>platform.openai.com/docs/models</a
									>
								{:else}
									See all available models at
									<a
										href="https://docs.anthropic.com/en/docs/about-claude/models"
										target="_blank"
										rel="noopener"
										class="underline hover:text-gray-700 dark:hover:text-gray-300"
										>docs.anthropic.com/en/docs/about-claude/models</a
									>
								{/if}
							</p>
						{/if}
					</div>
				{:else}
					<!-- Ollama: free-text model input -->
					<div>
						<div class="flex items-center gap-2 mb-1">
							<label for="model" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
								Model
							</label>
							{@render sourceBadge(getSource('ai_model'))}
						</div>
						<input
							id="model"
							type="text"
							bind:value={model}
							placeholder="llama3.2"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							Leave empty for the default model. Run <code
								class="bg-gray-100 dark:bg-gray-700 px-1 rounded">ollama list</code
							> to see installed models.
						</p>
					</div>
				{/if}

				<!-- Base URL (ollama only) -->
				{#if needsBaseUrl}
					<div>
						<div class="flex items-center gap-2 mb-1">
							<label
								for="base-url"
								class="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								Base URL
							</label>
							{@render sourceBadge(getSource('ai_base_url'))}
						</div>
						<input
							id="base-url"
							type="text"
							bind:value={baseUrl}
							placeholder="http://localhost:11434"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
						/>
					</div>
				{/if}

				<!-- Advanced settings -->
				<div class="border-t border-gray-200 dark:border-gray-700 pt-4">
					<button
						class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
						onclick={() => (showAdvanced = !showAdvanced)}
					>
						<span
							class="{showAdvanced ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'} text-xs"
						></span>
						Advanced Settings
					</button>

					{#if showAdvanced}
						<div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
							<div>
								<div class="flex items-center gap-2 mb-1">
									<label
										for="timeout"
										class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									>
										Timeout (seconds)
									</label>
									{@render sourceBadge(getSource('ai_timeout'))}
								</div>
								<input
									id="timeout"
									type="number"
									bind:value={timeout}
									min="5"
									max="300"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
								/>
							</div>
							<div>
								<div class="flex items-center gap-2 mb-1">
									<label
										for="max-text"
										class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									>
										Max Text Length
									</label>
									{@render sourceBadge(getSource('ai_max_text_length'))}
								</div>
								<input
									id="max-text"
									type="number"
									bind:value={maxTextLength}
									min="100"
									max="100000"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
								/>
							</div>
							<div>
								<div class="flex items-center gap-2 mb-1">
									<label
										for="max-pages"
										class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									>
										Max Vision Pages
									</label>
									{@render sourceBadge(getSource('ai_max_pages'))}
								</div>
								<input
									id="max-pages"
									type="number"
									bind:value={maxPages}
									min="1"
									max="50"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
								/>
							</div>
							<div>
								<div class="flex items-center gap-2 mb-1">
									<label
										for="vision-dpi"
										class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									>
										Vision DPI
									</label>
									{@render sourceBadge(getSource('ai_vision_dpi'))}
								</div>
								<input
									id="vision-dpi"
									type="number"
									bind:value={visionDpi}
									min="72"
									max="600"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
								/>
							</div>
							<div class="sm:col-span-2">
								<div class="flex items-center gap-2 mb-1">
									<label
										for="vision-model"
										class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									>
										Vision Model Override
									</label>
									{@render sourceBadge(getSource('ai_vision_model'))}
								</div>
								<input
									id="vision-model"
									type="text"
									bind:value={visionModel}
									placeholder="Leave empty to use the main model"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
								/>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Action buttons -->
			<div class="flex items-center gap-3 pt-2 border-t border-gray-200 dark:border-gray-700">
				<button class="btn btn-primary" onclick={handleSave} disabled={saving}>
					{#if saving}
						<span class="i-lucide-loader-2 animate-spin mr-2"></span>
					{:else}
						<span class="i-lucide-save mr-2"></span>
					{/if}
					Save
				</button>

				{#if provider !== 'none'}
					<button class="btn btn-secondary" onclick={handleTest} disabled={testing}>
						{#if testing}
							<span class="i-lucide-loader-2 animate-spin mr-2"></span>
						{:else}
							<span class="i-lucide-plug mr-2"></span>
						{/if}
						Test Connection
					</button>
				{/if}

				<button
					class="btn btn-secondary ml-auto text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
					onclick={handleReset}
					disabled={resetting}
					title="Remove all database-stored settings and revert to environment variable / default values"
				>
					{#if resetting}
						<span class="i-lucide-loader-2 animate-spin mr-2"></span>
					{:else}
						<span class="i-lucide-rotate-ccw mr-2"></span>
					{/if}
					Reset to Defaults
				</button>
			</div>
		</div>
	{/if}
</div>

{#snippet sourceBadge(source: string)}
	{#if source === 'database'}
		<span
			class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400"
		>
			database
		</span>
	{:else if source === 'env'}
		<span
			class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
		>
			env
		</span>
	{:else}
		<span
			class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500"
		>
			default
		</span>
	{/if}
{/snippet}
