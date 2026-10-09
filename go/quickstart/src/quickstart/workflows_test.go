package quickstart

import (
	"encoding/json"
	"slices"
	"testing"

	"github.com/agnt5dev/sdk-go/agnt5"
)

func TestDigestInputSchemaLeavesDefaultedLimitOptional(t *testing.T) {
	worker := agnt5.NewWorker("quickstart-schema-test")
	if err := agnt5.RegisterWorkflow(worker, "digest", DigestWorkflow); err != nil {
		t.Fatal(err)
	}
	if err := agnt5.RegisterFunction(worker, "fetch_top_ids", FetchTopIDsFunction); err != nil {
		t.Fatal(err)
	}

	components := worker.Components()
	if len(components) != 2 {
		t.Fatalf("registered %d components, want 2", len(components))
	}
	for _, component := range components {
		properties, ok := component.InputSchema["properties"].(map[string]any)
		if !ok {
			t.Fatalf("%s: missing input properties", component.Name)
		}
		limit, ok := properties["limit"].(map[string]any)
		if !ok || limit["type"] != "integer" {
			t.Fatalf("%s: limit schema = %#v, want integer", component.Name, properties["limit"])
		}
		required, _ := component.InputSchema["required"].([]string)
		if component.Name == "digest" && slices.Contains(required, "limit") {
			t.Fatal("digest limit must be optional so omitted input uses the workflow's default")
		}
		if component.Name == "fetch_top_ids" && !slices.Contains(required, "limit") {
			t.Fatal("standalone fetch_top_ids must still require its limit")
		}
	}
}

func TestDigestInputJSON(t *testing.T) {
	for _, test := range []struct {
		name  string
		input string
		limit int
		wire  string
	}{
		{name: "omitted", input: `{}`, limit: 0, wire: `{}`},
		{name: "explicit zero", input: `{"limit":0}`, limit: 0, wire: `{}`},
		{name: "explicit positive", input: `{"limit":3}`, limit: 3, wire: `{"limit":3}`},
	} {
		t.Run(test.name, func(t *testing.T) {
			var input DigestInput
			if err := json.Unmarshal([]byte(test.input), &input); err != nil {
				t.Fatal(err)
			}
			if input.Limit != test.limit {
				t.Fatalf("decoded limit = %d, want %d", input.Limit, test.limit)
			}
			wire, err := json.Marshal(input)
			if err != nil {
				t.Fatal(err)
			}
			if string(wire) != test.wire {
				t.Fatalf("encoded input = %s, want %s", wire, test.wire)
			}
		})
	}
}
