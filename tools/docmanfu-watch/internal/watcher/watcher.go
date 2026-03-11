package watcher

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/ui"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/uploader"
)

const debounceDuration = 500 * time.Millisecond

func isSkipped(name string) bool {
	base := filepath.Base(name)
	if strings.HasPrefix(base, ".") {
		return true
	}
	for _, suffix := range []string{"~", ".tmp", ".part", ".crdownload"} {
		if strings.HasSuffix(base, suffix) {
			return true
		}
	}
	return false
}

func Watch(dir string, up *uploader.Uploader) error {
	w, err := fsnotify.NewWatcher()
	if err != nil {
		return fmt.Errorf("create watcher: %w", err)
	}
	defer w.Close()

	if err := w.Add(dir); err != nil {
		return fmt.Errorf("watch dir: %w", err)
	}

	ui.Info("Watching %s", dir)

	var (
		mu       sync.Mutex
		timers   = make(map[string]*time.Timer)
		uploaded = make(map[string]bool)
	)

	for {
		select {
		case event, ok := <-w.Events:
			if !ok {
				return nil
			}
			if event.Op&(fsnotify.Create|fsnotify.Write) == 0 {
				continue
			}
			path := event.Name
			if isSkipped(path) {
				continue
			}
			ext := strings.ToLower(filepath.Ext(path))
			if !uploader.SupportedExtensions[ext] {
				continue
			}

			mu.Lock()
			if t, exists := timers[path]; exists {
				t.Reset(debounceDuration)
				mu.Unlock()
				continue
			}
			timers[path] = time.AfterFunc(debounceDuration, func() {
				mu.Lock()
				delete(timers, path)
				if uploaded[path] {
					mu.Unlock()
					return
				}
				uploaded[path] = true
				mu.Unlock()

				uploadFile(up, path)
			})
			mu.Unlock()

		case err, ok := <-w.Errors:
			if !ok {
				return nil
			}
			ui.Error("watcher: %v", err)
		}
	}
}

func Scan(dir string, up *uploader.Uploader) error {
	var found []string
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		if isSkipped(path) {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if uploader.SupportedExtensions[ext] {
			found = append(found, path)
		}
		return nil
	})
	if err != nil {
		return err
	}

	if len(found) == 0 {
		ui.Info("No supported files found in %s", dir)
		return nil
	}

	fmt.Printf("\nFound %d file(s):\n", len(found))
	for _, f := range found {
		fmt.Printf("  %s\n", f)
	}

	fmt.Print("\nUpload all? [y/N]: ")
	reader := bufio.NewReader(os.Stdin)
	line, _ := reader.ReadString('\n')
	if strings.ToLower(strings.TrimSpace(line)) != "y" {
		ui.Info("Aborted.")
		return nil
	}

	for _, f := range found {
		uploadFile(up, f)
	}
	return nil
}

func uploadFile(up *uploader.Uploader, path string) {
	ui.Uploading("%s", filepath.Base(path))
	result, err := up.Upload(path)
	if err != nil {
		ui.Error("%s: %v", filepath.Base(path), err)
		return
	}
	ui.Success("%s → id=%s job=%s", result.OriginalName, result.ID, result.JobID)
}
