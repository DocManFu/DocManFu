<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { listBills, updateBillStatus } from '$lib/api/bills.js';
	import type { BillListItem, BillStatus } from '$lib/types/index.js';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { toasts } from '$lib/stores/toast.js';

	type TabKey = BillStatus | 'all';

	const tabs: { key: TabKey; label: string }[] = [
		{ key: 'unpaid', label: 'Unpaid' },
		{ key: 'paid', label: 'Paid' },
		{ key: 'dismissed', label: 'Dismissed' },
		{ key: 'all', label: 'All' },
	];

	let bills = $state<BillListItem[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let activeTab = $state<TabKey>('unpaid');
	let offset = $state(0);
	let limit = 50;

	function isOverdue(bill: BillListItem): boolean {
		if (!bill.bill_due_date || bill.bill_status !== 'unpaid') return false;
		return new Date(bill.bill_due_date) < new Date(new Date().toISOString().split('T')[0]);
	}

	function displayName(bill: BillListItem): string {
		return bill.ai_generated_name || bill.original_name;
	}

	function company(bill: BillListItem): string {
		return (bill.ai_metadata?.company as string) || '—';
	}

	function docDate(bill: BillListItem): string {
		return (bill.ai_metadata?.date as string) || '—';
	}

	function amount(bill: BillListItem): string {
		return (bill.ai_metadata?.amount as string) || '—';
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '—';
		return new Date(iso).toLocaleDateString();
	}

	async function fetchBills() {
		loading = true;
		try {
			const res = await listBills(activeTab, offset, limit);
			bills = res.bills;
			total = res.total;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load bills');
		} finally {
			loading = false;
		}
	}

	function switchTab(tab: TabKey) {
		activeTab = tab;
		offset = 0;
		fetchBills();
	}

	function handlePageChange(newOffset: number) {
		offset = newOffset;
		fetchBills();
	}

	async function markPaid(bill: BillListItem, e: Event) {
		e.stopPropagation();
		try {
			await updateBillStatus(bill.id, 'paid');
			toasts.success('Marked as paid');
			fetchBills();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to update');
		}
	}

	async function markDismissed(bill: BillListItem, e: Event) {
		e.stopPropagation();
		try {
			await updateBillStatus(bill.id, 'dismissed');
			toasts.success('Dismissed');
			fetchBills();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to update');
		}
	}

	async function markUnpaid(bill: BillListItem, e: Event) {
		e.stopPropagation();
		try {
			await updateBillStatus(bill.id, 'unpaid');
			toasts.success('Marked as unpaid');
			fetchBills();
		} catch (err) {
			toasts.error(err instanceof Error ? err.message : 'Failed to update');
		}
	}

	onMount(fetchBills);
</script>

<svelte:head>
	<title>Bills - DocManFu</title>
</svelte:head>

<div class="page-container">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Bills</h1>
	</div>

	<!-- Tabs -->
	<div class="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
		{#each tabs as tab}
			<button
				class="px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
					{activeTab === tab.key
					? 'border-brand-600 text-brand-600 dark:border-brand-400 dark:text-brand-400'
					: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
				onclick={() => switchTab(tab.key)}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	{#if loading}
		<LoadingSpinner />
	{:else if bills.length === 0}
		<EmptyState
			icon="i-lucide-receipt"
			title="No {activeTab === 'all' ? '' : activeTab} bills"
			description={activeTab === 'unpaid'
				? 'Upload a bill PDF and it will appear here after AI processing.'
				: 'No bills match this filter.'}
		/>
	{:else}
		<div class="card overflow-hidden">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">From</th>
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Date</th>
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
							>Document</th
						>
						<th class="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Amount</th
						>
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
							>Due Date</th
						>
						<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Status</th>
						<th class="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
							>Actions</th
						>
					</tr>
				</thead>
				<tbody>
					{#each bills as bill (bill.id)}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
						<tr
							class="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/30 cursor-pointer transition-colors
								{isOverdue(bill) ? 'bg-red-50 dark:bg-red-900/10' : ''}"
							onclick={() => goto(`/documents/${bill.id}`)}
						>
							<td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{company(bill)}</td
							>
							<td class="px-4 py-3 text-gray-600 dark:text-gray-400">{docDate(bill)}</td>
							<td class="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-xs truncate"
								>{displayName(bill)}</td
							>
							<td class="px-4 py-3 text-right font-mono text-gray-900 dark:text-gray-100"
								>{amount(bill)}</td
							>
							<td class="px-4 py-3">
								{#if bill.bill_due_date}
									<span
										class={isOverdue(bill)
											? 'text-red-600 dark:text-red-400 font-medium'
											: 'text-gray-600 dark:text-gray-400'}
									>
										{formatDate(bill.bill_due_date)}
										{#if isOverdue(bill)}
											<span class="text-xs ml-1">(overdue)</span>
										{/if}
									</span>
								{:else}
									<span class="text-gray-400">—</span>
								{/if}
							</td>
							<td class="px-4 py-3">
								{#if bill.bill_status === 'unpaid'}
									<span
										class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
									>
										Unpaid
									</span>
								{:else if bill.bill_status === 'paid'}
									<span
										class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
									>
										Paid
									</span>
								{:else if bill.bill_status === 'dismissed'}
									<span
										class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
									>
										Dismissed
									</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-right">
								<div class="flex items-center justify-end gap-1">
									{#if bill.bill_status === 'unpaid'}
										<button
											class="btn-ghost btn-sm text-xs text-green-600 hover:text-green-700 dark:text-green-400"
											onclick={(e) => markPaid(bill, e)}
										>
											Paid
										</button>
										<button
											class="btn-ghost btn-sm text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400"
											onclick={(e) => markDismissed(bill, e)}
										>
											Not a Bill
										</button>
									{:else}
										<button
											class="btn-ghost btn-sm text-xs text-amber-600 hover:text-amber-700 dark:text-amber-400"
											onclick={(e) => markUnpaid(bill, e)}
										>
											Mark Unpaid
										</button>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mt-4">
			<Pagination {total} {offset} {limit} onchange={handlePageChange} />
		</div>
	{/if}
</div>
