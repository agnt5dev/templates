// E2B sandbox client for secure code execution.
//
// The Go SDK has no E2B-specific client (unlike Python's e2b_code_interpreter
// package) and agnt5.NewHTTPSandbox speaks AGNT5's own fixed REST protocol,
// not E2B's — so this implements a small client directly against E2B's
// public HTTP API using net/http.
//
// Sandbox lifecycle (create/kill) goes through E2B's documented control-plane
// API at https://api.e2b.dev. Command execution and file I/O go through the
// sandbox's own envd HTTP surface, exposed at https://{port}-{sandboxID}.e2b.dev.
// envd's real interface is richer than shown here (it supports streaming
// process output); this client implements a simplified synchronous
// request/response wrapper sufficient for "write files, run pytest, read the
// result" — verify against https://e2b.dev/docs and adjust endpoints if E2B
// has changed its API since this was written.
package coding_agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"
)

const (
	e2bControlPlaneURL = "https://api.e2b.dev"
	e2bDefaultTemplate = "base"
	e2bEnvdPort        = 49983
)

type e2bClient struct {
	apiKey     string
	httpClient *http.Client
}

func NewE2BClient(apiKey string) *e2bClient {
	return &e2bClient{apiKey: apiKey, httpClient: &http.Client{Timeout: 60 * time.Second}}
}

func (c *e2bClient) sandboxHost(sandboxID string) string {
	return fmt.Sprintf("https://%d-%s.e2b.dev", e2bEnvdPort, sandboxID)
}

// createSandbox creates a new E2B sandbox and returns its ID.
func (c *e2bClient) createSandbox(ctx context.Context) (string, error) {
	body, _ := json.Marshal(map[string]any{
		"templateID": e2bDefaultTemplate,
		"timeout":    300,
	})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, e2bControlPlaneURL+"/sandboxes", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("X-API-Key", c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("E2B sandbox creation failed (HTTP %d): %s", resp.StatusCode, respBody)
	}

	var result struct {
		SandboxID string `json:"sandboxID"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}
	if result.SandboxID == "" {
		return "", fmt.Errorf("E2B did not return a sandbox ID")
	}
	return result.SandboxID, nil
}

// killSandbox terminates a sandbox. Errors are non-fatal for callers that
// just want a best-effort cleanup.
func (c *e2bClient) killSandbox(ctx context.Context, sandboxID string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, e2bControlPlaneURL+"/sandboxes/"+sandboxID, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-API-Key", c.apiKey)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

// writeFile writes a file into the sandbox filesystem via envd's file upload
// endpoint.
func (c *e2bClient) writeFile(ctx context.Context, sandboxID, path, content string) error {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	part, err := writer.CreateFormFile("file", path)
	if err != nil {
		return err
	}
	if _, err := part.Write([]byte(content)); err != nil {
		return err
	}
	if err := writer.Close(); err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.sandboxHost(sandboxID)+"/files?path="+path, &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("writing %s failed (HTTP %d): %s", path, resp.StatusCode, body)
	}
	return nil
}

// readFile reads a file from the sandbox filesystem.
func (c *e2bClient) readFile(ctx context.Context, sandboxID, path string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.sandboxHost(sandboxID)+"/files?path="+path, nil)
	if err != nil {
		return "", err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("reading %s failed (HTTP %d)", path, resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	return string(body), err
}

type e2bCommandResult struct {
	ExitCode int    `json:"exit_code"`
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	Success  bool   `json:"success"`
}

// runCommand runs a shell command in the sandbox and waits for it to finish.
func (c *e2bClient) runCommand(ctx context.Context, sandboxID, command string, timeout time.Duration) (e2bCommandResult, error) {
	body, _ := json.Marshal(map[string]any{
		"cmd":     "sh",
		"args":    []string{"-c", command},
		"timeout": int(timeout.Seconds()),
	})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.sandboxHost(sandboxID)+"/process", bytes.NewReader(body))
	if err != nil {
		return e2bCommandResult{}, err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: timeout + 10*time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return e2bCommandResult{}, err
	}
	defer resp.Body.Close()

	var result e2bCommandResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		body, _ := io.ReadAll(resp.Body)
		return e2bCommandResult{}, fmt.Errorf("unexpected response from sandbox process endpoint: %s", body)
	}
	result.Success = result.ExitCode == 0
	return result, nil
}

// listFiles lists files and directories at path in the sandbox.
func (c *e2bClient) listFiles(ctx context.Context, sandboxID, path string) ([]string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.sandboxHost(sandboxID)+"/dir?path="+path, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var entries []struct {
		Name string `json:"name"`
		Type string `json:"type"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&entries); err != nil {
		return nil, err
	}
	names := make([]string, len(entries))
	for i, e := range entries {
		kind := "FILE"
		if e.Type == "dir" {
			kind = "DIR"
		}
		names[i] = kind + ": " + e.Name
	}
	return names, nil
}
