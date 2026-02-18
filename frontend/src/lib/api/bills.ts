import { apiFetch } from './client.js';
import type { BillsListResponse, BillStatus } from '$lib/types/index.js';

export function listBills(
	status: BillStatus | 'all' = 'unpaid',
	offset = 0,
	limit = 50,
): Promise<BillsListResponse> {
	const params = new URLSearchParams({ status, offset: String(offset), limit: String(limit) });
	return apiFetch<BillsListResponse>(`/api/bills?${params}`);
}

export function updateBillStatus(
	id: string,
	status: BillStatus,
): Promise<{ detail: string; bill_status: string; bill_paid_at: string | null }> {
	return apiFetch(`/api/bills/${id}/status`, {
		method: 'PATCH',
		body: JSON.stringify({ status }),
	});
}

export function updateBillDueDate(
	id: string,
	due_date: string | null,
): Promise<{ detail: string; bill_due_date: string | null }> {
	return apiFetch(`/api/bills/${id}/due-date`, {
		method: 'PATCH',
		body: JSON.stringify({ due_date }),
	});
}
