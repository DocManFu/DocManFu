<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.js';
	import { checkSetupNeeded, login } from '$lib/api/auth.js';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let checking = $state(true);

	onMount(async () => {
		try {
			const needed = await checkSetupNeeded();
			if (needed) {
				goto('/auth/setup');
				return;
			}
		} catch {
			// API not available — stay on login
		}
		checking = false;
	});

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;
		try {
			const response = await login(username, password);
			auth.login(response);
			goto('/documents');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Login failed';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Sign In - DocManFu</title>
</svelte:head>

{#if checking}
	<div class="min-h-screen flex items-center justify-center">
		<div class="i-lucide-loader-2 animate-spin text-2xl text-gray-400"></div>
	</div>
{:else}
	<div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
		<div class="w-full max-w-sm">
			<div class="text-center mb-8">
				<div class="flex items-center justify-center gap-2 text-2xl font-bold text-brand-600 mb-2">
					<span class="i-lucide-folder-open text-3xl"></span>
					DocManFu
				</div>
				<p class="text-gray-500 dark:text-gray-400">Sign in to your account</p>
			</div>

			<form onsubmit={handleSubmit} class="bg-white dark:bg-gray-800 shadow-sm rounded-xl p-6 space-y-4 border border-gray-200 dark:border-gray-700">
				{#if error}
					<div class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm">
						{error}
					</div>
				{/if}

				<div>
					<label for="username" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						Username or Email
					</label>
					<input
						id="username"
						type="text"
						bind:value={username}
						required
						autocomplete="username"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
					/>
				</div>

				<div>
					<label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						Password
					</label>
					<input
						id="password"
						type="password"
						bind:value={password}
						required
						autocomplete="current-password"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
					/>
				</div>

				<button
					type="submit"
					disabled={loading || !username || !password}
					class="w-full btn btn-primary py-2.5"
				>
					{#if loading}
						<span class="i-lucide-loader-2 animate-spin mr-2"></span>
					{/if}
					Sign In
				</button>
			</form>
		</div>
	</div>
{/if}
