<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { isAdmin } from '$lib/stores/auth.js';
	import { toasts } from '$lib/stores/toast.js';
	import {
		listUsers,
		createUser,
		updateUser,
		deactivateUser,
		resetUserPassword,
	} from '$lib/api/auth.js';
	import type { AdminUser } from '$lib/types/index.js';

	let users = $state<AdminUser[]>([]);
	let loading = $state(true);

	// Create user form
	let showCreateForm = $state(false);
	let newUsername = $state('');
	let newEmail = $state('');
	let newPassword = $state('');
	let newRole = $state('user');
	let createError = $state('');
	let creating = $state(false);

	// Reset password
	let resetUserId = $state<string | null>(null);
	let resetPassword = $state('');

	onMount(() => {
		if (!$isAdmin) {
			goto('/documents');
			return;
		}
		loadUsers();
	});

	async function loadUsers() {
		loading = true;
		try {
			users = await listUsers();
		} catch (err) {
			toasts.error('Failed to load users');
		} finally {
			loading = false;
		}
	}

	async function handleCreateUser(e: SubmitEvent) {
		e.preventDefault();
		createError = '';
		creating = true;
		try {
			await createUser(newUsername, newEmail, newPassword, newRole);
			toasts.success('User created');
			showCreateForm = false;
			newUsername = '';
			newEmail = '';
			newPassword = '';
			newRole = 'user';
			await loadUsers();
		} catch (err) {
			createError = err instanceof Error ? err.message : 'Failed to create user';
		} finally {
			creating = false;
		}
	}

	async function handleToggleActive(user: AdminUser) {
		try {
			await updateUser(user.id, { is_active: !user.is_active });
			toasts.success(`User ${user.is_active ? 'deactivated' : 'activated'}`);
			await loadUsers();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to update user');
		}
	}

	async function handleRoleChange(user: AdminUser, role: string) {
		try {
			await updateUser(user.id, { role });
			toasts.success('Role updated');
			await loadUsers();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to update role');
		}
	}

	async function handleResetPassword(userId: string) {
		if (!resetPassword || resetPassword.length < 8) {
			toasts.error('Password must be at least 8 characters');
			return;
		}
		try {
			await resetUserPassword(userId, resetPassword);
			toasts.success('Password reset');
			resetUserId = null;
			resetPassword = '';
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to reset password');
		}
	}
</script>

<svelte:head>
	<title>User Management - DocManFu</title>
</svelte:head>

<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<!-- Admin tabs -->
	<div class="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
		<a
			href="/admin/users"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-brand-500 text-brand-600 dark:text-brand-400"
		>
			Users
		</a>
		<a
			href="/admin/settings"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
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
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">User Management</h1>
		<button class="btn btn-primary" onclick={() => (showCreateForm = !showCreateForm)}>
			<span class="i-lucide-user-plus mr-2"></span>
			Create User
		</button>
	</div>

	{#if showCreateForm}
		<div
			class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 mb-6"
		>
			<h2 class="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">Create New User</h2>
			<form onsubmit={handleCreateUser} class="space-y-4">
				{#if createError}
					<div
						class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm"
					>
						{createError}
					</div>
				{/if}

				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
					<div>
						<label
							for="new-username"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
							>Username</label
						>
						<input
							id="new-username"
							type="text"
							bind:value={newUsername}
							required
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
						/>
					</div>
					<div>
						<label
							for="new-email"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label
						>
						<input
							id="new-email"
							type="email"
							bind:value={newEmail}
							required
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
						/>
					</div>
					<div>
						<label
							for="new-password"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
							>Password</label
						>
						<input
							id="new-password"
							type="password"
							bind:value={newPassword}
							required
							minlength="8"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
						/>
					</div>
					<div>
						<label
							for="new-role"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label
						>
						<select
							id="new-role"
							bind:value={newRole}
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
						>
							<option value="user">User</option>
							<option value="admin">Admin</option>
							<option value="readonly">Read Only</option>
						</select>
					</div>
				</div>

				<div class="flex gap-2">
					<button type="submit" disabled={creating} class="btn btn-primary">
						{#if creating}
							<span class="i-lucide-loader-2 animate-spin mr-2"></span>
						{/if}
						Create
					</button>
					<button type="button" class="btn btn-secondary" onclick={() => (showCreateForm = false)}>
						Cancel
					</button>
				</div>
			</form>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div class="i-lucide-loader-2 animate-spin text-2xl text-gray-400"></div>
		</div>
	{:else}
		<div
			class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden"
		>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">User</th>
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Role</th>
						<th class="text-center px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Docs</th>
						<th class="text-center px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
							>Status</th
						>
						<th class="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
							>Actions</th
						>
					</tr>
				</thead>
				<tbody>
					{#each users as user}
						<tr class="border-b border-gray-100 dark:border-gray-700/50 last:border-0">
							<td class="px-4 py-3">
								<div class="font-medium text-gray-900 dark:text-gray-100">{user.username}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">{user.email}</div>
							</td>
							<td class="px-4 py-3">
								<select
									value={user.role}
									onchange={(e) => handleRoleChange(user, (e.target as HTMLSelectElement).value)}
									class="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
								>
									<option value="admin">Admin</option>
									<option value="user">User</option>
									<option value="readonly">Read Only</option>
								</select>
							</td>
							<td class="px-4 py-3 text-center text-gray-600 dark:text-gray-400"
								>{user.document_count}</td
							>
							<td class="px-4 py-3 text-center">
								{#if user.is_active}
									<span
										class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
									>
										Active
									</span>
								{:else}
									<span
										class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
									>
										Inactive
									</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-right">
								<div class="flex items-center justify-end gap-1">
									<button
										class="btn-icon"
										title={user.is_active ? 'Deactivate' : 'Activate'}
										onclick={() => handleToggleActive(user)}
									>
										{#if user.is_active}
											<span class="i-lucide-user-x text-red-500"></span>
										{:else}
											<span class="i-lucide-user-check text-green-500"></span>
										{/if}
									</button>
									<button
										class="btn-icon"
										title="Reset password"
										onclick={() => {
											resetUserId = resetUserId === user.id ? null : user.id;
											resetPassword = '';
										}}
									>
										<span class="i-lucide-key"></span>
									</button>
								</div>

								{#if resetUserId === user.id}
									<div class="mt-2 flex gap-2">
										<input
											type="password"
											placeholder="New password"
											bind:value={resetPassword}
											class="flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
										/>
										<button
											class="btn btn-primary text-xs px-2 py-1"
											onclick={() => handleResetPassword(user.id)}
										>
											Reset
										</button>
									</div>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
