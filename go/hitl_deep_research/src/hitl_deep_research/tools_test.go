package hitl_deep_research

import (
	"context"
	"net"
	"net/url"
	"strings"
	"testing"
)

func parseURL(raw string) (*url.URL, error) { return url.Parse(raw) }

// TestDialRefusesPrivateAddresses covers the policy at the point it is
// enforced. Literal addresses resolve without DNS, so this runs offline and
// exercises the same function every real connection and redirect goes
// through -- including the cloud metadata endpoint that motivated it.
func TestDialRefusesPrivateAddresses(t *testing.T) {
	for _, addr := range []string{
		"127.0.0.1:80",
		"169.254.169.254:80", // cloud metadata
		"10.0.0.8:443",
		"192.168.1.1:80",
		"[::1]:80",
		"[fe80::1]:80",
		"0.0.0.0:80",
	} {
		conn, err := dialPublicAddressOnly(context.Background(), "tcp", addr)
		if conn != nil {
			conn.Close()
		}
		if err == nil || !strings.Contains(err.Error(), "private address") {
			t.Errorf("dial %s: err = %v, want a private-address refusal", addr, err)
		}
	}
}

func TestIsPrivateAddress(t *testing.T) {
	private := []string{"127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.0.1", "169.254.169.254", "::1", "fe80::1", "fd00::1", "0.0.0.0"}
	for _, s := range private {
		if !isPrivateAddress(net.ParseIP(s)) {
			t.Errorf("%s should be treated as private", s)
		}
	}
	public := []string{"1.1.1.1", "8.8.8.8", "93.184.216.34", "2606:4700:4700::1111"}
	for _, s := range public {
		if isPrivateAddress(net.ParseIP(s)) {
			t.Errorf("%s should be treated as public", s)
		}
	}
}

func TestCheckResearchSchemeRejectsNonHTTP(t *testing.T) {
	for _, raw := range []string{"file:///etc/passwd", "ftp://example.com/x", "gopher://example.com", "http://"} {
		u, err := parseURL(raw)
		if err != nil {
			continue
		}
		if err := checkResearchScheme(u); err == nil {
			t.Errorf("%s accepted, want rejection", raw)
		}
	}
}
