<script lang="ts">
	import type { DocumentDetail, DocumentUpdateRequest } from '$lib/types/index.js';
	import { formatFileSize, formatDate, formatDocumentType } from '$lib/utils/format.js';

	const DOCUMENT_TYPES = [
		'bill',
		'bank_statement',
		'medical',
		'insurance',
		'tax',
		'invoice',
		'receipt',
		'legal',
		'correspondence',
		'report',
		'other'
	] as const;

	interface Props {
		document: DocumentDetail;
		onupdate?: (fields: DocumentUpdateRequest) => Promise<void>;
	}

	let { document: doc, onupdate }: Props = $props();

	let editing = $state(false);
	let saving = $state(false);

	// Edit state
	let editType = $state('');
	let editCompany = $state('');
	let editDate = $state('');
	let editAmount = $state('');
	let editAccount = $state('');
	let editSummary = $state('');

	interface MetaItem {
		label: string;
		value: string;
		icon: string;
	}

	let metaItems = $derived<MetaItem[]>([
		{ label: 'Type', value: formatDocumentType(doc.document_type), icon: 'i-lucide-tag' },
		{ label: 'Size', value: formatFileSize(doc.file_size), icon: 'i-lucide-hard-drive' },
		{ label: 'Uploaded', value: formatDate(doc.upload_date), icon: 'i-lucide-calendar' },
		...(doc.processed_date
			? [{ label: 'Processed', value: formatDate(doc.processed_date), icon: 'i-lucide-check-circle' }]
			: []),
		{ label: 'MIME', value: doc.mime_type, icon: 'i-lucide-file-type' }
	]);

	let aiMeta = $derived(doc.ai_metadata as Record<string, unknown> | null);

	function startEdit() {
		editType = doc.document_type || '';
		const meta = aiMeta || {};
		editCompany = (meta.company as string) || '';
		editDate = (meta.date as string) || '';
		editAmount = (meta.amount as string) || '';
		editAccount = (meta.account_number as string) || '';
		editSummary = (meta.summary as string) || '';
		editing = true;
	}

	function cancelEdit() {
		editing = false;
	}

	async function saveEdit() {
		if (!onupdate) return;
		saving = true;
		try {
			const updatedMeta: Record<string, unknown> = { ...(aiMeta || {}) };
			updatedMeta.company = editCompany || undefined;
			updatedMeta.date = editDate || undefined;
			updatedMeta.amount = editAmount || undefined;
			updatedMeta.account_number = editAccount || undefined;
			updatedMeta.summary = editSummary || undefined;

			await onupdate({
				document_type: editType || undefined,
				ai_metadata: updatedMeta
			});
			editing = false;
		} finally {
			saving = false;
		}
	}
</script>

<div class="space-y-4">
	<div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
		{#each metaItems as item}
			<div class="text-sm">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 mb-0.5">
					<span class="{item.icon} text-xs"></span>
					{item.label}
				</div>
				<div class="text-gray-900 dark:text-gray-100 font-medium">{item.value}</div>
			</div>
		{/each}
	</div>

	{#if aiMeta || editing}
		<div class="border-t border-gray-100 dark:border-gray-700 pt-4">
			<div class="flex items-center justify-between mb-3">
				<h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1">
					<span class="i-lucide-sparkles text-brand-500"></span>
					AI Analysis
				</h4>
				{#if onupdate && !editing}
					<button class="btn-icon" title="Edit AI analysis" onclick={startEdit}>
						<span class="i-lucide-pencil text-sm"></span>
					</button>
				{/if}
			</div>

			{#if editing}
				<div class="space-y-3 text-sm">
					<div>
						<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-doc-type">Document Type</label>
						<select id="edit-doc-type" class="input-base w-full" bind:value={editType}>
							<option value="">Unknown</option>
							{#each DOCUMENT_TYPES as t}
								<option value={t}>{formatDocumentType(t)}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-company">Company</label>
						<input id="edit-company" type="text" class="input-base w-full" bind:value={editCompany} />
					</div>
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-date">Date</label>
							<input id="edit-date" type="text" class="input-base w-full" bind:value={editDate} />
						</div>
						<div>
							<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-amount">Amount</label>
							<input id="edit-amount" type="text" class="input-base w-full" bind:value={editAmount} />
						</div>
					</div>
					<div>
						<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-account">Account</label>
						<input id="edit-account" type="text" class="input-base w-full" bind:value={editAccount} />
					</div>
					<div>
						<label class="block text-gray-500 dark:text-gray-400 mb-1" for="edit-summary">Summary</label>
						<textarea id="edit-summary" class="input-base w-full" rows="3" bind:value={editSummary}></textarea>
					</div>
					<div class="flex items-center gap-2 pt-1">
						<button class="btn-primary btn-sm" onclick={saveEdit} disabled={saving}>
							{saving ? 'Saving...' : 'Save'}
						</button>
						<button class="btn-ghost btn-sm" onclick={cancelEdit} disabled={saving}>Cancel</button>
					</div>
				</div>
			{:else}
				<div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
					{#if aiMeta?.company}
						<div>
							<div class="text-gray-500 dark:text-gray-400">Company</div>
							<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.company}</div>
						</div>
					{/if}
					{#if aiMeta?.date}
						<div>
							<div class="text-gray-500 dark:text-gray-400">Document Date</div>
							<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.date}</div>
						</div>
					{/if}
					{#if aiMeta?.amount}
						<div>
							<div class="text-gray-500 dark:text-gray-400">Amount</div>
							<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.amount}</div>
						</div>
					{/if}
					{#if aiMeta?.account_number}
						<div>
							<div class="text-gray-500 dark:text-gray-400">Account</div>
							<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.account_number}</div>
						</div>
					{/if}
					{#if aiMeta?.summary}
						<div class="col-span-2 sm:col-span-3">
							<div class="text-gray-500 dark:text-gray-400">Summary</div>
							<div class="text-gray-900 dark:text-gray-100">{aiMeta.summary}</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>
