// E2B sandbox client for secure code execution.
//
// The Go SDK has no E2B-specific client (unlike Python's e2b_code_interpreter
// package) and agnt5.NewHTTPSandbox speaks AGNT5's own fixed REST protocol,
// not E2B's — so this implements a small client directly against E2B's
// public HTTP API using net/http.
//
// Sandbox lifecycle (create/kill) goes through E2B's control-plane API at
// https://api.e2b.dev. Files and commands go through the sandbox's own agent,
// envd, at https://{port}-{sandboxID}.e2b.app:
//
//   - files: POST/GET /files?path=…&username=user (multipart upload)
//   - commands: the Connect RPC process.Process/Start, which streams the
//     process's output and ends with its exit code (see runCommand)
//
// Every envd call runs as the sandbox's default user "user", so relative
// paths (main.py, test.py) and command working directories both resolve to
// /home/user. Sandboxes created with secure access also need an
// X-Access-Token header; the default ones used here do not.
package coding_agent

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"time"
)

const (
	e2bControlPlaneURL = "https://api.e2b.dev"
	// code-interpreter-v1 is the image the Python and TypeScript templates get
	// from E2B's code-interpreter SDK. It ships pytest; "base" does not, so
	// every test run there failed with "pytest: command not found".
	e2bDefaultTemplate = "code-interpreter-v1"
	e2bEnvdPort        = 49983
	e2bSandboxDomain   = "e2b.app"
	e2bSandboxUser     = "user"
	e2bSandboxHome     = "/home/user"
)

type e2bClient struct {
	apiKey     string
	httpClient *http.Client
}

func NewE2BClient(apiKey string) *e2bClient {
	return &e2bClient{apiKey: apiKey, httpClient: &http.Client{Timeout: 60 * time.Second}}
}

func (c *e2bClient) sandboxHost(sandboxID string) string {
	return fmt.Sprintf("https://%d-%s.%s", e2bEnvdPort, sandboxID, e2bSandboxDomain)
}

// setEnvdUser makes envd act as the sandbox's default user. Without it, files
// and commands can resolve against different users' home directories.
func setEnvdUser(req *http.Request) {
	req.Header.Set("Authorization", "Basic "+base64.StdEncoding.EncodeToString([]byte(e2bSandboxUser+":")))
}

func envdFilesURL(host, path string) string {
	return host + "/files?" + url.Values{"path": {path}, "username": {e2bSandboxUser}}.Encode()
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

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, envdFilesURL(c.sandboxHost(sandboxID), path), &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	setEnvdUser(req)

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
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, envdFilesURL(c.sandboxHost(sandboxID), path), nil)
	if err != nil {
		return "", err
	}
	setEnvdUser(req)
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
//
// envd has no plain request/response endpoint for this. process.Process/Start
// is a Connect server-streaming RPC: the request is one enveloped JSON message,
// and the reply is a sequence of them — a start event, stdout/stderr chunks
// (base64, which encoding/json decodes into []byte), and an end event with
// the exit code — followed by an end-of-stream frame. Each envelope is a flags
// byte, a big-endian uint32 length, then the JSON payload.
func (c *e2bClient) runCommand(ctx context.Context, sandboxID, command string, timeout time.Duration) (e2bCommandResult, error) {
	msg, _ := json.Marshal(map[string]any{
		"process": map[string]any{
			"cmd":  "/bin/bash",
			"args": []string{"-l", "-c", command},
			"cwd":  e2bSandboxHome,
		},
	})
	var body bytes.Buffer
	body.WriteByte(0)
	_ = binary.Write(&body, binary.BigEndian, uint32(len(msg)))
	body.Write(msg)

	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	req, err := http.NewRequestWithContext(runCtx, http.MethodPost, c.sandboxHost(sandboxID)+"/process.Process/Start", &body)
	if err != nil {
		return e2bCommandResult{}, err
	}
	req.Header.Set("Content-Type", "application/connect+json")
	req.Header.Set("Connect-Protocol-Version", "1")
	setEnvdUser(req)

	resp, err := (&http.Client{Timeout: timeout + 10*time.Second}).Do(req)
	if err != nil {
		return e2bCommandResult{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return e2bCommandResult{}, fmt.Errorf("sandbox process start failed (HTTP %d): %s", resp.StatusCode, respBody)
	}

	var stdout, stderr bytes.Buffer
	exitCode, ended := 0, false
	header := make([]byte, 5)
	for {
		if _, err := io.ReadFull(resp.Body, header); err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			return e2bCommandResult{}, fmt.Errorf("reading sandbox process stream: %w", err)
		}
		payload := make([]byte, binary.BigEndian.Uint32(header[1:]))
		if _, err := io.ReadFull(resp.Body, payload); err != nil {
			return e2bCommandResult{}, fmt.Errorf("reading sandbox process stream: %w", err)
		}
		if header[0]&0x02 != 0 {
			// End of stream. A failed RPC reports its error here.
			var eos struct {
				Error *struct {
					Code    string `json:"code"`
					Message string `json:"message"`
				} `json:"error"`
			}
			if json.Unmarshal(payload, &eos) == nil && eos.Error != nil {
				return e2bCommandResult{}, fmt.Errorf("sandbox process failed: %s: %s", eos.Error.Code, eos.Error.Message)
			}
			break
		}
		var m struct {
			Event struct {
				Data *struct {
					Stdout []byte `json:"stdout"`
					Stderr []byte `json:"stderr"`
				} `json:"data"`
				End *struct {
					ExitCode int `json:"exitCode"`
				} `json:"end"`
			} `json:"event"`
		}
		if err := json.Unmarshal(payload, &m); err != nil {
			return e2bCommandResult{}, fmt.Errorf("decoding sandbox process event: %w", err)
		}
		if d := m.Event.Data; d != nil {
			stdout.Write(d.Stdout)
			stderr.Write(d.Stderr)
		}
		if e := m.Event.End; e != nil {
			exitCode, ended = e.ExitCode, true
		}
	}
	if !ended {
		return e2bCommandResult{}, fmt.Errorf("sandbox process stream ended without an exit status")
	}
	return e2bCommandResult{
		ExitCode: exitCode,
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
		Success:  exitCode == 0,
	}, nil
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
