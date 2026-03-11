package config

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	Endpoint string `json:"endpoint"`
	APIKey   string `json:"api_key"`
}

func configPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".config", "docmanfu", "config.json"), nil
}

func Load() (*Config, error) {
	path, err := configPath()
	if err != nil {
		return &Config{}, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &Config{}, nil
		}
		return &Config{}, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return &Config{}, err
	}
	return &cfg, nil
}

func Save(cfg *Config) error {
	path, err := configPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0600)
}

func Prompt(cfg *Config) error {
	reader := bufio.NewReader(os.Stdin)

	if cfg.Endpoint == "" {
		fmt.Print("DocManFu endpoint URL (e.g. http://localhost:8100): ")
		line, err := reader.ReadString('\n')
		if err != nil {
			return err
		}
		cfg.Endpoint = strings.TrimRight(strings.TrimSpace(line), "/")
	}

	if cfg.APIKey == "" {
		fmt.Print("API key: ")
		line, err := reader.ReadString('\n')
		if err != nil {
			return err
		}
		cfg.APIKey = strings.TrimSpace(line)
	}

	return nil
}
