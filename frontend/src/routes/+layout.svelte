<script lang="ts">
	import 'virtual:uno.css';
	import '../app.css';
	import Navbar from '$lib/components/layout/Navbar.svelte';
	import ToastContainer from '$lib/components/shared/ToastContainer.svelte';
	import JobTracker from '$lib/components/jobs/JobTracker.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<div class="min-h-screen flex flex-col">
	<Navbar />
	<main class="flex-1">
		{@render children()}
	</main>
	<ToastContainer />
	<JobTracker />
</div>
