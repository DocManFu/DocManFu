<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import 'virtual:uno.css';
	import '../app.css';
	import Navbar from '$lib/components/layout/Navbar.svelte';
	import ToastContainer from '$lib/components/shared/ToastContainer.svelte';
	import JobTracker from '$lib/components/jobs/JobTracker.svelte';
	import KeyboardShortcuts from '$lib/components/shared/KeyboardShortcuts.svelte';
	import ShortcutsHelp from '$lib/components/shared/ShortcutsHelp.svelte';
	import { jobStore } from '$lib/stores/jobs.js';
	import { auth, isAuthenticated } from '$lib/stores/auth.js';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	let ready = $state(false);

	onMount(() => {
		auth.loadFromStorage();
		ready = true;
	});

	// Auth guard: redirect to login if not authenticated (except auth routes)
	$effect(() => {
		if (!ready) return;
		const path = $page.url.pathname;
		const isAuthRoute = path.startsWith('/auth');
		const authenticated = $isAuthenticated;

		if (!authenticated && !isAuthRoute) {
			goto('/auth/login');
		}
	});

	// Init job store only when authenticated
	let jobStoreActive = false;
	$effect(() => {
		if ($isAuthenticated && !jobStoreActive) {
			jobStore.init();
			jobStoreActive = true;
		} else if (!$isAuthenticated && jobStoreActive) {
			jobStore.destroy();
			jobStoreActive = false;
		}
	});
</script>

{#if !ready}
	<div class="min-h-screen flex items-center justify-center">
		<div class="i-lucide-loader-2 animate-spin text-2xl text-gray-400"></div>
	</div>
{:else if $page.url.pathname.startsWith('/auth')}
	{@render children()}
	<ToastContainer />
{:else if $isAuthenticated}
	<KeyboardShortcuts />
	<div class="min-h-screen flex flex-col">
		<Navbar />
		<main class="flex-1">
			{@render children()}
		</main>
		<ToastContainer />
		<JobTracker />
		<ShortcutsHelp />
	</div>
{/if}
