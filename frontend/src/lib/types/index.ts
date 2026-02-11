export interface Tag {
	id: string;
	name: string;
	color: string;
}

export interface DocumentListItem {
	id: string;
	filename: string;
	original_name: string;
	ai_generated_name: string | null;
	document_type: string | null;
	file_size: number;
	upload_date: string;
	processed_date: string | null;
	tags: Tag[];
	bill_status: string | null;
	bill_due_date: string | null;
	bill_paid_at: string | null;
}

export interface DocumentDetail extends DocumentListItem {
	content_text: string | null;
	ai_metadata: Record<string, unknown> | null;
	file_path: string;
	mime_type: string;
	created_at: string;
	updated_at: string;
}

export interface PaginatedResponse {
	documents: DocumentListItem[];
	total: number;
	offset: number;
	limit: number;
}

export interface UploadResponse {
	id: string;
	filename: string;
	original_name: string;
	file_size: number;
	upload_date: string;
	job_id: string;
	message: string;
}

export interface JobStatusResponse {
	id: string;
	document_id: string;
	job_type: 'ocr' | 'ai_analysis' | 'file_organization';
	status: 'pending' | 'processing' | 'completed' | 'failed';
	progress: number;
	error_message: string | null;
	created_at: string;
	started_at: string | null;
	completed_at: string | null;
	result_data: Record<string, unknown> | null;
}

export interface DocumentUpdateRequest {
	original_name?: string;
	tags?: string[];
}

export interface ReprocessResponse {
	jobs: Array<{ job_id: string; job_type: string }>;
	message: string;
}

export type DocumentType =
	| 'bill'
	| 'bank_statement'
	| 'medical'
	| 'insurance'
	| 'tax'
	| 'invoice'
	| 'receipt'
	| 'legal'
	| 'correspondence'
	| 'report'
	| 'other';

export interface ListDocumentsParams {
	offset?: number;
	limit?: number;
	document_type?: string;
	tag?: string;
	date_from?: string;
	date_to?: string;
	sort_by?: 'upload_date' | 'name' | 'size' | 'type';
	sort_order?: 'asc' | 'desc';
}

export interface SearchDocumentsParams {
	q: string;
	offset?: number;
	limit?: number;
	document_type?: string;
	tag?: string;
}

// --- Search with highlights ---

export interface SearchResultItem extends DocumentListItem {
	headline: string | null;
	rank: number;
}

export interface SearchPaginatedResponse {
	documents: SearchResultItem[];
	total: number;
	offset: number;
	limit: number;
}

// --- Tag management ---

export interface TagWithCount extends Tag {
	document_count: number;
}

export interface TagCreateRequest {
	name: string;
	color?: string;
}

export interface TagUpdateRequest {
	name?: string;
	color?: string;
}

export interface TagMergeRequest {
	source_tag_ids: string[];
	target_tag_id: string;
}

// --- Bulk operations ---

export interface BulkTagRequest {
	document_ids: string[];
	add_tags: string[];
	remove_tags: string[];
}

export interface BulkDeleteRequest {
	document_ids: string[];
}

export interface BulkReprocessRequest {
	document_ids: string[];
}

// --- Bills ---

export type BillStatus = 'unpaid' | 'paid' | 'dismissed';

export interface BillListItem {
	id: string;
	filename: string;
	original_name: string;
	ai_generated_name: string | null;
	document_type: string | null;
	file_size: number;
	upload_date: string;
	bill_status: string | null;
	bill_due_date: string | null;
	bill_paid_at: string | null;
	ai_metadata: Record<string, unknown> | null;
}

export interface BillsListResponse {
	bills: BillListItem[];
	total: number;
	offset: number;
	limit: number;
}
