<script lang="ts">
	import { auth, currentUser } from '$lib/stores/auth.js';
	import { generateApiKey, revokeApiKey, changePassword } from '$lib/api/auth.js';
	import { toasts } from '$lib/stores/toast.js';

	// API key state
	let generatedKey = $state<string | null>(null);
	let copied = $state(false);
	let generatingKey = $state(false);
	let revokingKey = $state(false);

	// Change password state
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let changingPassword = $state(false);

	async function handleGenerateKey() {
		generatingKey = true;
		generatedKey = null;
		try {
			const res = await generateApiKey();
			generatedKey = res.api_key;
			if ($currentUser) {
				auth.updateUser({ ...$currentUser, has_api_key: true });
			}
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to generate API key');
		} finally {
			generatingKey = false;
		}
	}

	async function handleRevokeKey() {
		revokingKey = true;
		generatedKey = null;
		try {
			await revokeApiKey();
			if ($currentUser) {
				auth.updateUser({ ...$currentUser, has_api_key: false });
			}
			toasts.success('API key revoked');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to revoke API key');
		} finally {
			revokingKey = false;
		}
	}

	async function copyKey() {
		if (!generatedKey) return;
		try {
			await navigator.clipboard.writeText(generatedKey);
			copied = true;
			setTimeout(() => (copied = false), 2000);
		} catch {
			toasts.error('Could not copy to clipboard');
		}
	}

	async function handleChangePassword() {
		if (newPassword !== confirmPassword) {
			toasts.error('New passwords do not match');
			return;
		}
		if (newPassword.length < 8) {
			toasts.error('Password must be at least 8 characters');
			return;
		}
		changingPassword = true;
		try {
			await changePassword(currentPassword, newPassword);
			toasts.success('Password changed');
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to change password');
		} finally {
			changingPassword = false;
		}
	}
</script>

<div class="max-w-2xl mx-auto px-4 py-8 space-y-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Profile</h1>

	<!-- Account info -->
	<section class="card p-6 space-y-3">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Account</h2>
		{#if $currentUser}
			<dl class="space-y-2 text-sm">
				<div class="flex gap-4">
					<dt class="w-24 text-gray-500 dark:text-gray-400 shrink-0">Username</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{$currentUser.username}</dd>
				</div>
				<div class="flex gap-4">
					<dt class="w-24 text-gray-500 dark:text-gray-400 shrink-0">Email</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{$currentUser.email}</dd>
				</div>
				<div class="flex gap-4">
					<dt class="w-24 text-gray-500 dark:text-gray-400 shrink-0">Role</dt>
					<dd>
						<span class="inline-block px-2 py-0.5 rounded text-xs font-medium
							{$currentUser.role === 'admin'
								? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
								: $currentUser.role === 'readonly'
									? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
									: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'}">
							{$currentUser.role}
						</span>
					</dd>
				</div>
			</dl>
		{/if}
	</section>

	<!-- API Key -->
	<section class="card p-6 space-y-4">
		<div>
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">API Key</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
				Use this key with the <code class="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">docmanfu</code> CLI tool or any API client.
				Pass it as <code class="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">Authorization: Bearer &lt;key&gt;</code>.
			</p>
		</div>

		{#if generatedKey}
			<!-- Show newly generated key -->
			<div class="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20 p-4 space-y-3">
				<p class="text-sm font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
					<span class="i-lucide-triangle-alert text-base"></span>
					Copy this key now — it won't be shown again.
				</p>
				<div class="flex gap-2">
					<input
						type="text"
						readonly
						value={generatedKey}
						class="flex-1 font-mono text-sm px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 focus:outline-none"
						onclick={(e) => (e.target as HTMLInputElement).select()}
					/>
					<button class="btn-secondary flex items-center gap-1.5" onclick={copyKey}>
						{#if copied}
							<span class="i-lucide-check"></span>
							Copied
						{:else}
							<span class="i-lucide-copy"></span>
							Copy
						{/if}
					</button>
				</div>
			</div>
		{/if}

		<div class="flex flex-wrap gap-2">
			{#if $currentUser?.has_api_key}
				<button
					class="btn-primary flex items-center gap-1.5"
					onclick={handleGenerateKey}
					disabled={generatingKey}
				>
					<span class="i-lucide-refresh-cw"></span>
					{generatingKey ? 'Generating…' : 'Regenerate Key'}
				</button>
				<button
					class="btn-danger flex items-center gap-1.5"
					onclick={handleRevokeKey}
					disabled={revokingKey}
				>
					<span class="i-lucide-trash-2"></span>
					{revokingKey ? 'Revoking…' : 'Revoke Key'}
				</button>
			{:else}
				<p class="text-sm text-gray-500 dark:text-gray-400 w-full">No API key is currently active.</p>
				<button
					class="btn-primary flex items-center gap-1.5"
					onclick={handleGenerateKey}
					disabled={generatingKey}
				>
					<span class="i-lucide-key"></span>
					{generatingKey ? 'Generating…' : 'Generate API Key'}
				</button>
			{/if}
		</div>
	</section>

	<!-- Change password -->
	<section class="card p-6 space-y-4">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Change Password</h2>
		<div class="space-y-3">
			<div>
				<label for="current-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					Current password
				</label>
				<input
					id="current-password"
					type="password"
					class="input w-full"
					bind:value={currentPassword}
					autocomplete="current-password"
				/>
			</div>
			<div>
				<label for="new-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					New password
				</label>
				<input
					id="new-password"
					type="password"
					class="input w-full"
					bind:value={newPassword}
					autocomplete="new-password"
				/>
			</div>
			<div>
				<label for="confirm-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					Confirm new password
				</label>
				<input
					id="confirm-password"
					type="password"
					class="input w-full"
					bind:value={confirmPassword}
					autocomplete="new-password"
				/>
			</div>
			<button
				class="btn-primary"
				onclick={handleChangePassword}
				disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
			>
				{changingPassword ? 'Saving…' : 'Change Password'}
			</button>
		</div>
	</section>
</div>
