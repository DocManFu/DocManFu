<script lang="ts">
	import { page } from '$app/stores';
</script>

<div class="page-container">
	<div class="flex flex-col items-center justify-center py-20 text-center">
		<span class="i-lucide-alert-triangle text-5xl text-gray-400 mb-4"></span>
		<h1 class="text-2xl font-bold text-gray-900 mb-2">
			{$page.status}
		</h1>
		<p class="text-gray-600 mb-6">
			{$page.error?.message ?? 'Something went wrong'}
		</p>
		<a href="/documents" class="btn-primary no-underline"> Go to Documents </a>
	</div>
</div>
