// --- Auth ---

export interface User {
	id: string;
	username: string;
	email: string;
	role: 'admin' | 'user' | 'readonly';
	is_active: boolean;
	has_api_key: boolean;
	created_at: string;
}

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	user: User;
}

export interface LoginRequest {
	username: string;
	password: string;
}

export interface SetupRequest {
	username: string;
	email: string;
	password: string;
}

export interface AdminUser extends User {
	document_count: number;
}

// --- Documents & Tags ---

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
	mime_type: string;
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

export interface JobListItem extends JobStatusResponse {
	document_name: string;
}

export interface JobListResponse {
	jobs: JobListItem[];
	total: number;
	offset: number;
	limit: number;
}

export interface JobListParams {
	status?: string;
	job_type?: string;
	sort_order?: 'asc' | 'desc';
	offset?: number;
	limit?: number;
}

export interface DocumentUpdateRequest {
	original_name?: string;
	tags?: string[];
	ai_generated_name?: string;
	document_type?: string;
	ai_metadata?: Record<string, unknown>;
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
	untagged?: string;
	untyped?: string;
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

// --- AI Settings ---

export type AIProvider = 'none' | 'openai' | 'anthropic' | 'ollama';

export interface AISettingValue {
	value: string | null;
	source: 'database' | 'env' | 'default';
	is_set?: boolean;
}

export type AISettings = Record<string, AISettingValue>;

export interface AISettingsUpdate {
	ai_provider?: string;
	ai_api_key?: string;
	ai_model?: string;
	ai_base_url?: string;
	ai_max_text_length?: number;
	ai_timeout?: number;
	ai_max_pages?: number;
	ai_vision_dpi?: number;
	ai_vision_model?: string;
}

export interface TestConnectionResult {
	success: boolean;
	message: string;
	detail?: string;
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
