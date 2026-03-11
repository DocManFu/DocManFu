package ui

import (
	"fmt"
	"os/exec"
	"runtime"
)

// ANSI color codes — disabled on Windows where cmd.exe doesn't support VT sequences.
var (
	reset  = "\033[0m"
	bold   = "\033[1m"
	cyan   = "\033[36m"
	green  = "\033[32m"
	yellow = "\033[33m"
	red    = "\033[31m"
	gray   = "\033[90m"
)

func init() {
	if runtime.GOOS == "windows" {
		reset, bold, cyan, green, yellow, red, gray = "", "", "", "", "", "", ""
	}
}

func Info(format string, args ...any) {
	fmt.Printf(cyan+"[INFO] "+reset+format+"\n", args...)
}

func Warn(format string, args ...any) {
	fmt.Printf(yellow+"[WARN] "+reset+format+"\n", args...)
}

func Error(format string, args ...any) {
	fmt.Printf(red+"[ERROR] "+reset+format+"\n", args...)
}

func Success(format string, args ...any) {
	fmt.Printf(green+"[OK]   "+reset+format+"\n", args...)
}

func Uploading(format string, args ...any) {
	fmt.Printf(bold+gray+"[UP]   "+reset+format+"\n", args...)
}

func OpenBrowser(url string) {
	var cmd string
	var args []string

	switch runtime.GOOS {
	case "darwin":
		cmd = "open"
		args = []string{url}
	case "windows":
		cmd = "cmd"
		args = []string{"/c", "start", url}
	default:
		cmd = "xdg-open"
		args = []string{url}
	}

	if err := exec.Command(cmd, args...).Start(); err != nil {
		Warn("could not open browser: %v", err)
	}
}
