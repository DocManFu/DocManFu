/**
 * Helpers for the Gmail-style search syntax (parsed server-side in
 * app/core/search_query.py): editing the query string and describing operators.
 */

import type { SearchTerm } from '$lib/types/index.js';

export const DOCUMENT_TYPES = [
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
	'other',
];

export interface OperatorInfo {
	key: string;
	description: string;
	example: string;
	/** Fixed values offered by autocomplete */
	values?: string[];
}

/** Operators shown in autocomplete and the search tips (aliases work too, see the backend). */
export const OPERATORS: OperatorInfo[] = [
	{ key: 'title', description: 'Name contains', example: 'title:utah' },
	{ key: 'ocr', description: 'Scanned text contains', example: 'ocr:ford' },
	{ key: 'tag', description: 'Has tag', example: 'tag:bill' },
	{ key: 'type', description: 'Document type', example: 'type:receipt', values: DOCUMENT_TYPES },
	{ key: 'company', description: 'Company / sender', example: 'company:"rocky mountain"' },
	{ key: 'notes', description: 'Your notes contain', example: 'notes:warranty' },
	{
		key: 'is',
		description: 'Status',
		example: 'is:unpaid',
		values: ['unpaid', 'overdue', 'paid', 'dismissed', 'bill', 'untagged', 'untyped'],
	},
	{
		key: 'has',
		description: 'Has a field',
		example: 'has:notes',
		values: ['notes', 'tags', 'text', 'type', 'due'],
	},
	{ key: 'after', description: 'Dated on or after', example: 'after:2024-06' },
	{ key: 'before', description: 'Dated before', example: 'before:2024' },
	{ key: 'date', description: 'Dated in year/month/day', example: 'date:2024-03' },
	{
		key: 'newer_than',
		description: 'Dated within the last…',
		example: 'newer_than:30d',
		values: ['7d', '30d', '3m', '6m', '1y'],
	},
	{
		key: 'older_than',
		description: 'Dated more than … ago',
		example: 'older_than:1y',
		values: ['30d', '6m', '1y', '2y', '5y'],
	},
];

/** Alias -> canonical key, mirroring OPERATORS in app/core/search_query.py. */
export const OPERATOR_ALIASES: Record<string, string> = {
	name: 'title',
	text: 'ocr',
	content: 'ocr',
	from: 'company',
	note: 'notes',
	since: 'after',
	year: 'date',
};

export const TERM_LABELS: Record<string, string> = {
	title: 'Title',
	ocr: 'Text',
	tag: 'Tag',
	type: 'Type',
	company: 'Company',
	notes: 'Notes',
	is: 'Is',
	has: 'Has',
	after: 'After',
	before: 'Before',
	date: 'Date',
	newer_than: 'Newer than',
	older_than: 'Older than',
};

/** Quote a value if it contains whitespace: `city newsletter` -> `"city newsletter"`. */
export function quoteValue(value: string): string {
	return /\s/.test(value) ? `"${value.replace(/"/g, '')}"` : value;
}

export function formatTerm(key: string, value: string, negated = false): string {
	return `${negated ? '-' : ''}${key}:${quoteValue(value)}`;
}

/** Collapse whitespace outside quotes (quoted values are kept exactly). */
function tidy(q: string): string {
	return q
		.split(/("[^"]*"?)/)
		.map((part, i) => (i % 2 ? part : part.replace(/\s+/g, ' ')))
		.join('')
		.trim();
}

/** Close a dangling quote, or anything appended would become part of its value. */
function closeQuote(q: string): string {
	return (q.match(/"/g) ?? []).length % 2 ? `${q}"` : q;
}

/** Remove the text at [start, end) — used to drop one filter chip. */
export function removeSpan(q: string, start: number, end: number): string {
	return tidy(q.slice(0, start) + ' ' + q.slice(end));
}

/**
 * Add `key:value` (or its negation) to the query. Replaces an existing term
 * for the same key+value, so toggling include/exclude doesn't stack.
 */
export function addTerm(
	q: string,
	terms: SearchTerm[],
	key: string,
	value: string,
	negated = false,
): string {
	const existing = terms
		.filter((t) => t.key === key && t.value.toLowerCase() === value.toLowerCase())
		.sort((a, b) => b.start - a.start);
	for (const t of existing) q = q.slice(0, t.start) + q.slice(t.end);
	return tidy(`${closeQuote(q)} ${formatTerm(key, value, negated)}`);
}

/** Fold legacy URL params (?document_type=&tag=&untagged=&untyped=) into the query. */
export function legacyParamsToQuery(q: string, params: URLSearchParams): string {
	const extra: string[] = [];
	const type = params.get('document_type');
	if (type) extra.push(formatTerm('type', type));
	for (const tag of (params.get('tag') ?? '').split(',')) {
		if (tag.trim()) extra.push(formatTerm('tag', tag.trim()));
	}
	if (params.get('untagged') === 'true') extra.push('is:untagged');
	if (params.get('untyped') === 'true') extra.push('is:untyped');
	return extra.length ? tidy([closeQuote(q), ...extra].join(' ')) : q;
}

/** The whitespace-delimited token around `caret` (quotes keep spaces inside a token). */
export function tokenAt(q: string, caret: number): { start: number; end: number; text: string } {
	const re = /-?(?:[A-Za-z_]+:)?"[^"]*"?|\S+/g;
	let m: RegExpExecArray | null;
	while ((m = re.exec(q))) {
		const start = m.index;
		const end = start + m[0].length;
		if (caret >= start && caret <= end) return { start, end, text: m[0] };
		if (start > caret) break;
	}
	return { start: caret, end: caret, text: '' };
}

/**
 * Words worth highlighting in a matching document: the free text plus `ocr:`
 * values, minus operators, exclusions (`-word`) and `OR`.
 */
export function highlightWords(q: string, terms: SearchTerm[]): string {
	let text = q;
	for (const t of [...terms].sort((a, b) => b.start - a.start)) {
		text = text.slice(0, t.start) + ' ' + text.slice(t.end);
	}
	const words = (text.match(/-?"[^"]*"?|\S+/g) ?? [])
		.filter((w) => !w.startsWith('-') && w !== 'OR')
		.map((w) => w.replace(/"/g, ''));
	for (const t of terms) if (t.key === 'ocr' && !t.negated) words.push(t.value);
	return tidy(words.join(' '));
}
