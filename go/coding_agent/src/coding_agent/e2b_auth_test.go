package coding_agent

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/agnt5dev/sdk-go/agnt5"
)

// fakeE2B stands in for E2B's control plane and every sandbox's envd. Like
// E2B, envd refuses a call that doesn't carry the sandbox's access token.
type fakeE2B struct {
	t   *testing.T
	srv *httptest.Server

	mu         sync.Mutex
	created    int
	tokens     map[string]string // running sandboxes and their tokens
	files      map[string]string // "<sandbox>/<path>" -> content
	lookups    int
	failWrites func(sandboxID string) bool
}

func newFakeE2B(t *testing.T) *fakeE2B {
	f := &fakeE2B{t: t, tokens: map[string]string{}, files: map[string]string{}}
	f.srv = httptest.NewServer(http.HandlerFunc(f.serve))
	t.Cleanup(f.srv.Close)
	return f
}

// client is a worker's E2B client. Each call gives a fresh one, as a worker
// that resumes a run would have.
func (f *fakeE2B) client() *e2bClient {
	c := NewE2BClient("test-key")
	c.controlPlane = f.srv.URL
	c.host = func(sandboxID string) string { return f.srv.URL + "/envd/" + sandboxID }
	return c
}

func (f *fakeE2B) running() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	ids := []string{}
	for id := range f.tokens {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

func (f *fakeE2B) serve(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if rest, ok := strings.CutPrefix(r.URL.Path, "/envd/"); ok {
		sandboxID, path, _ := strings.Cut(rest, "/")
		f.envd(w, r, sandboxID, "/"+path)
		return
	}
	if r.Header.Get("X-API-Key") != "test-key" {
		http.Error(w, "invalid API key", http.StatusUnauthorized)
		return
	}
	sandboxID := strings.TrimPrefix(r.URL.Path, "/sandboxes/")
	switch {
	case r.Method == http.MethodPost && r.URL.Path == "/sandboxes":
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["secure"] != true {
			f.t.Errorf("sandbox created without secure access: %v", body)
		}
		f.created++
		id := fmt.Sprintf("sbx-%d", f.created)
		f.tokens[id] = "token-" + id
		_ = json.NewEncoder(w).Encode(map[string]string{"sandboxID": id, "envdAccessToken": f.tokens[id]})
	case r.Method == http.MethodGet && sandboxID != r.URL.Path:
		f.lookups++
		token, ok := f.tokens[sandboxID]
		if !ok {
			http.Error(w, "sandbox not found", http.StatusNotFound)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]string{"sandboxID": sandboxID, "envdAccessToken": token})
	case r.Method == http.MethodDelete && sandboxID != r.URL.Path:
		delete(f.tokens, sandboxID)
		w.WriteHeader(http.StatusNoContent)
	default:
		http.NotFound(w, r)
	}
}

func (f *fakeE2B) envd(w http.ResponseWriter, r *http.Request, sandboxID, path string) {
	token, ok := f.tokens[sandboxID]
	if !ok {
		http.Error(w, "sandbox not found", http.StatusBadGateway)
		return
	}
	if r.Header.Get("X-Access-Token") != token {
		http.Error(w, `{"code":401,"message":"missing signature query parameter"}`, http.StatusUnauthorized)
		return
	}
	if user, _, _ := r.BasicAuth(); user != e2bSandboxUser {
		http.Error(w, "call is not made as the sandbox user", http.StatusForbidden)
		return
	}
	key := sandboxID + "/" + r.URL.Query().Get("path")
	switch {
	case path == "/files" && r.Method == http.MethodPost:
		if f.failWrites != nil && f.failWrites(sandboxID) {
			http.Error(w, "write failed", http.StatusInternalServerError)
			return
		}
		file, _, err := r.FormFile("file")
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		content, _ := io.ReadAll(file)
		f.files[key] = string(content)
		_, _ = io.WriteString(w, "[]")
	case path == "/files" && r.Method == http.MethodGet:
		content, ok := f.files[key]
		if !ok {
			http.NotFound(w, r)
			return
		}
		_, _ = io.WriteString(w, content)
	case path == "/process.Process/Start":
		stdout := base64.StdEncoding.EncodeToString([]byte("1 passed\n"))
		writeConnectFrame(w, 0, `{"event":{"data":{"stdout":"`+stdout+`"}}}`)
		writeConnectFrame(w, 0, `{"event":{"end":{"exitCode":0}}}`)
		writeConnectFrame(w, 0x02, `{}`)
	default:
		http.NotFound(w, r)
	}
}

func writeConnectFrame(w io.Writer, flags byte, payload string) {
	header := make([]byte, 5)
	header[0] = flags
	binary.BigEndian.PutUint32(header[1:], uint32(len(payload)))
	_, _ = w.Write(header)
	_, _ = io.WriteString(w, payload)
}

// TestEnvdCallsCarryTheSandboxToken covers the calls the workflow makes:
// without the token E2B refuses each of them, so no run could get past its
// first sync.
func TestEnvdCallsCarryTheSandboxToken(t *testing.T) {
	f := newFakeE2B(t)
	c := f.client()
	ctx := context.Background()

	id, err := c.createSandbox(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.writeFile(ctx, id, "main.py", "x = 1\n"); err != nil {
		t.Fatalf("write: %v", err)
	}
	if got, err := c.readFile(ctx, id, "main.py"); err != nil || got != "x = 1\n" {
		t.Fatalf("read: %q, %v", got, err)
	}
	res, err := c.runCommand(ctx, id, "pytest test.py", time.Minute)
	if err != nil || !res.Success || !strings.Contains(res.Stdout, "1 passed") {
		t.Fatalf("run: %+v, %v", res, err)
	}
	if f.lookups != 0 {
		t.Errorf("looked up a token the create call already returned (%d lookups)", f.lookups)
	}
}

// TestTokenIsLookedUpOnceOnAnotherWorker: a run can resume on a worker that
// didn't create its sandbox. That worker fetches the token once and reuses it.
func TestTokenIsLookedUpOnceOnAnotherWorker(t *testing.T) {
	f := newFakeE2B(t)
	ctx := context.Background()
	id, err := f.client().createSandbox(ctx)
	if err != nil {
		t.Fatal(err)
	}

	resumed := f.client()
	for range 2 {
		if err := resumed.writeFile(ctx, id, "main.py", "x = 1\n"); err != nil {
			t.Fatalf("write: %v", err)
		}
	}
	if f.lookups != 1 {
		t.Errorf("%d token lookups, want 1", f.lookups)
	}

	if err := resumed.killSandbox(ctx, id); err != nil {
		t.Fatal(err)
	}
	if err := resumed.writeFile(ctx, id, "main.py", "x = 1\n"); err == nil {
		t.Error("write to a stopped sandbox succeeded")
	}
}

// TestSyncStopsTheSandboxItReplaces: when a sandbox stops taking writes, the
// sync moves to a new one and stops the old, so it doesn't hold one of the
// account's concurrent sandboxes until its timeout.
func TestSyncStopsTheSandboxItReplaces(t *testing.T) {
	f := newFakeE2B(t)
	c := f.client()
	ctx := &agnt5.Context{Context: context.Background()}
	old, err := c.createSandbox(ctx)
	if err != nil {
		t.Fatal(err)
	}
	f.failWrites = func(id string) bool { return id == old }

	res, err := codeSyncNode(ctx, c, "x = 1\n", "def test_x():\n    pass\n", old)
	if err != nil || !res.Success {
		t.Fatalf("sync: %+v, %v", res, err)
	}
	if res.SandboxID == old {
		t.Fatal("sync kept the sandbox that refused writes")
	}
	if got := f.running(); len(got) != 1 || got[0] != res.SandboxID {
		t.Errorf("running %v, want only %s", got, res.SandboxID)
	}
}

// TestFailedSyncLeavesNoSandboxRunning: a sync that gives up stops every
// sandbox it made and reports none, so the next attempt starts fresh.
func TestFailedSyncLeavesNoSandboxRunning(t *testing.T) {
	f := newFakeE2B(t)
	c := f.client()
	ctx := &agnt5.Context{Context: context.Background()}
	f.failWrites = func(string) bool { return true }

	res, err := codeSyncNode(ctx, c, "x = 1\n", "def test_x():\n    pass\n", "")
	if err != nil || res.Success {
		t.Fatalf("sync: %+v, %v", res, err)
	}
	if res.SandboxID != "" {
		t.Errorf("failed sync reported sandbox %s", res.SandboxID)
	}
	if got := f.running(); len(got) != 0 {
		t.Errorf("sandboxes left running: %v", got)
	}
	if f.created != 2 {
		t.Errorf("created %d sandboxes, want 2 (the first and one replacement)", f.created)
	}
}
