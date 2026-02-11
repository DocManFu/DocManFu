export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string
	) {
		super(detail);
		this.name = 'ApiError';
	}
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(path, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options?.headers
		}
	});

	if (!res.ok) {
		let detail = `Request failed with status ${res.status}`;
		try {
			const body = await res.json();
			if (body.detail) detail = body.detail;
		} catch {
			// use default message
		}
		throw new ApiError(res.status, detail);
	}

	if (res.status === 204) return undefined as T;
	return res.json();
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
	const formData = new FormData();
	formData.append('file', file);

	const res = await fetch(path, {
		method: 'POST',
		body: formData
	});

	if (!res.ok) {
		let detail = `Upload failed with status ${res.status}`;
		try {
			const body = await res.json();
			if (body.detail) detail = body.detail;
		} catch {
			// use default message
		}
		throw new ApiError(res.status, detail);
	}

	return res.json();
}
