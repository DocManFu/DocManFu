package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/config"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/ui"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/uploader"
	"github.com/DocManFu/DocManFu/tools/docmanfu-watch/internal/watcher"
)

func main() {
	var (
		flagEndpoint string
		flagKey      string
		flagPath     string
		flagScan     bool
	)

	root := &cobra.Command{
		Use:   "docmanfu",
		Short: "Watch a directory and auto-upload new documents to DocManFu",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load saved config
			cfg, err := config.Load()
			if err != nil {
				return fmt.Errorf("load config: %w", err)
			}

			// Apply flag overrides
			if flagEndpoint != "" {
				cfg.Endpoint = flagEndpoint
			}
			if flagKey != "" {
				cfg.APIKey = flagKey
			}

			// Prompt for missing fields
			if cfg.Endpoint == "" || cfg.APIKey == "" {
				if err := config.Prompt(cfg); err != nil {
					return fmt.Errorf("prompt: %w", err)
				}
			}

			// Persist config
			if err := config.Save(cfg); err != nil {
				ui.Warn("could not save config: %v", err)
			}

			// Resolve watch path
			watchPath := flagPath
			if watchPath == "" {
				watchPath, err = os.Getwd()
				if err != nil {
					return fmt.Errorf("get cwd: %w", err)
				}
			}

			up := uploader.New(cfg.Endpoint, cfg.APIKey)

			if flagScan {
				return watcher.Scan(watchPath, up)
			}

			ui.OpenBrowser(cfg.Endpoint)
			return watcher.Watch(watchPath, up)
		},
	}

	root.Flags().StringVarP(&flagEndpoint, "endpoint", "e", "", "DocManFu URL (saved to config)")
	root.Flags().StringVarP(&flagKey, "key", "k", "", "API key (saved to config)")
	root.Flags().StringVarP(&flagPath, "path", "p", "", "Directory to watch (default: current directory)")
	root.Flags().BoolVarP(&flagScan, "scan", "s", false, "Scan for existing files and prompt to upload")

	if err := root.Execute(); err != nil {
		os.Exit(1)
	}
}
