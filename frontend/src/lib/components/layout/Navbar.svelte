<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { theme } from '$lib/stores/theme.js';
	import { auth, currentUser, isAdmin } from '$lib/stores/auth.js';

	const navLinks = [
		{ href: '/documents', label: 'Documents', icon: 'i-lucide-files' },
		{ href: '/bills', label: 'Bills', icon: 'i-lucide-receipt' },
		{ href: '/upload', label: 'Upload', icon: 'i-lucide-upload' },
		{ href: '/search', label: 'Search', icon: 'i-lucide-search' },
		{ href: '/jobs', label: 'Jobs', icon: 'i-lucide-activity' },
		{ href: '/tags', label: 'Tags', icon: 'i-lucide-tags' }
	];

	function isActive(href: string, pathname: string): boolean {
		return pathname.startsWith(href);
	}

	let searchQuery = $state('');

	function handleSearchKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && searchQuery.trim()) {
			goto(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
		}
	}

	function handleLogout() {
		auth.logout();
		goto('/auth/login');
	}
</script>

<nav class="bg-white border-b border-gray-200 sticky top-0 z-40 dark:bg-gray-900 dark:border-gray-700">
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
		<div class="flex items-center justify-between h-16">
			<a href="/documents" class="flex items-center gap-2 text-lg font-bold text-brand-600 no-underline">
				<span class="i-lucide-folder-open text-xl"></span>
				DocManFu
			</a>

			<div class="flex items-center gap-1">
				{#each navLinks as link}
					<a
						href={link.href}
						class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium no-underline transition-colors
							{isActive(link.href, $page.url.pathname)
								? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
								: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200'}"
					>
						<span class={link.icon}></span>
						<span class="hidden sm:inline">{link.label}</span>
					</a>
				{/each}

				{#if $isAdmin}
					<a
						href="/admin/users"
						class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium no-underline transition-colors
							{isActive('/admin', $page.url.pathname)
								? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
								: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200'}"
						title="Admin"
					>
						<span class="i-lucide-shield"></span>
						<span class="hidden sm:inline">Admin</span>
					</a>
				{/if}

				<!-- Global search -->
				<div class="hidden md:block ml-2">
					<input
						id="global-search"
						type="text"
						class="w-40 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 bg-white text-gray-900 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400"
						placeholder="Search... (/)"
						bind:value={searchQuery}
						onkeydown={handleSearchKeydown}
					/>
				</div>

				<!-- Dark mode toggle -->
				<button
					class="btn-icon ml-1"
					title="Toggle dark mode"
					onclick={() => theme.toggle()}
				>
					{#if $theme === 'dark'}
						<span class="i-lucide-sun"></span>
					{:else}
						<span class="i-lucide-moon"></span>
					{/if}
				</button>

				<!-- User menu -->
				{#if $currentUser}
					<div class="flex items-center gap-2 ml-2 pl-2 border-l border-gray-200 dark:border-gray-700">
						<span class="text-sm text-gray-600 dark:text-gray-400 hidden sm:inline">
							{$currentUser.username}
						</span>
						<button
							class="btn-icon"
							title="Sign out"
							onclick={handleLogout}
						>
							<span class="i-lucide-log-out"></span>
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
</nav>
