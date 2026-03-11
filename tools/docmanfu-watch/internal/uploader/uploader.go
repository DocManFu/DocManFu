package uploader

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"os"
	"path/filepath"
	"strings"
)

var SupportedExtensions = map[string]bool{
	".pdf":  true,
	".jpg":  true,
	".jpeg": true,
	".png":  true,
	".tif":  true,
	".tiff": true,
	".webp": true,
}

var mimeTypes = map[string]string{
	".pdf":  "application/pdf",
	".jpg":  "image/jpeg",
	".jpeg": "image/jpeg",
	".png":  "image/png",
	".tif":  "image/tiff",
	".tiff": "image/tiff",
	".webp": "image/webp",
}

type UploadResult struct {
	ID           string `json:"id"`
	OriginalName string `json:"original_name"`
	FileSize     int64  `json:"file_size"`
	JobID        string `json:"job_id"`
}

type Uploader struct {
	Endpoint string
	APIKey   string
	client   *http.Client
}

func New(endpoint, apiKey string) *Uploader {
	return &Uploader{
		Endpoint: strings.TrimRight(endpoint, "/"),
		APIKey:   apiKey,
		client:   &http.Client{},
	}
}

func (u *Uploader) Upload(path string) (*UploadResult, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open file: %w", err)
	}
	defer f.Close()

	ext := strings.ToLower(filepath.Ext(path))
	mime, ok := mimeTypes[ext]
	if !ok {
		mime = "application/octet-stream"
	}

	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)

	h := make(textproto.MIMEHeader)
	h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="file"; filename="%s"`, filepath.Base(path)))
	h.Set("Content-Type", mime)
	part, err := w.CreatePart(h)
	if err != nil {
		return nil, fmt.Errorf("create form part: %w", err)
	}
	if _, err := io.Copy(part, f); err != nil {
		return nil, fmt.Errorf("copy file: %w", err)
	}
	w.Close()

	req, err := http.NewRequest("POST", u.Endpoint+"/api/documents/upload", &buf)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", w.FormDataContentType())
	req.Header.Set("Authorization", "Bearer "+u.APIKey)

	resp, err := u.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("upload request: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		var errResp struct {
			Detail string `json:"detail"`
		}
		if json.Unmarshal(body, &errResp) == nil && errResp.Detail != "" {
			return nil, fmt.Errorf("server error %d: %s", resp.StatusCode, errResp.Detail)
		}
		return nil, fmt.Errorf("server error %d: %s", resp.StatusCode, string(body))
	}

	var result UploadResult
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("parse response: %w", err)
	}
	return &result, nil
}
