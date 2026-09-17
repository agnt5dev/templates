package coding_agent

import (
	"strings"
	"testing"
)

// TestCappedOutputMarksEveryTruncation covers the two edges the review found:
// a stream that fills the buffer exactly, then keeps going, must still be
// marked; and the total, marker included, must never exceed the cap.
func TestCappedOutputMarksEveryTruncation(t *testing.T) {
	limit := maxCommandOutputBytes - len(truncationMarker)

	var exact cappedOutput
	exact.Write([]byte(strings.Repeat("x", limit)))
	if exact.truncated {
		t.Fatal("output at the limit was marked truncated before anything was dropped")
	}
	exact.Write([]byte("y"))
	if !exact.truncated || !strings.HasSuffix(exact.String(), truncationMarker) {
		t.Error("bytes were dropped after an exact fill without the marker being written")
	}

	var overflow cappedOutput
	overflow.Write([]byte(strings.Repeat("x", maxCommandOutputBytes*2)))
	if len(overflow.String()) > maxCommandOutputBytes {
		t.Errorf("output is %d bytes, over the %d cap", len(overflow.String()), maxCommandOutputBytes)
	}
	if !strings.HasSuffix(overflow.String(), truncationMarker) {
		t.Error("overflowing chunk was not marked")
	}
	if strings.Count(overflow.String(), truncationMarker) != 1 {
		t.Error("marker written more than once")
	}
	overflow.Write([]byte("more"))
	if strings.Count(overflow.String(), truncationMarker) != 1 {
		t.Error("a later chunk appended after truncation")
	}
}
