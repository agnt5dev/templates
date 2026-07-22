// Code review workflow: parallel context building, tech-stack detection,
// parallel per-file + security review, then a synthesized final report.
package code_reviewer

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"

	"agnt5.dev/sdk-go/agnt5"
)

const prSizeWarningThreshold = 30

type CodeReviewInput struct {
	PRURL     string `json:"pr_url"`
	TicketURL string `json:"ticket_url"`
}

type CodeReviewOutput struct {
	Status         string         `json:"status"`
	PRURL          string         `json:"pr_url"`
	TicketURL      string         `json:"ticket_url"`
	PRNumber       int            `json:"pr_number"`
	Repo           string         `json:"repo"`
	FilesReviewed  int            `json:"files_reviewed"`
	TotalFiles     int            `json:"total_files"`
	SecurityRisk   string         `json:"security_risk"`
	SeverityCounts map[string]int `json:"severity_counts"`
	TechStack      TechStack      `json:"tech_stack"`
	ContextSummary string         `json:"context_summary"`
	Report         string         `json:"report"`
	ReportFile     string         `json:"report_file,omitempty"`
}

func CodeReviewerWorkflow(ctx *agnt5.Context, in CodeReviewInput, model agnt5.LanguageModel, cfg AppConfig) (CodeReviewOutput, error) {
	ctx.Logger().Info("Starting code review workflow")

	// ── Step 1: context_builder_agent + fetch_pr_node in parallel ──────────
	// context_builder_agent autonomously calls its tools to build a rich
	// context summary of the PR and ticket requirements, while fetch_pr_node
	// gets the structured file data needed for per-file review steps. Both
	// run inside one Step since the Go SDK has no per-item parallel-step
	// helper yet — the whole pair is checkpointed together.
	ctx.Logger().Info("Step 1/4: Context Builder Agent + structured PR fetch (parallel)")

	type step1Result struct {
		contextSummary string
		prData         PRData
	}
	step1, err := agnt5.Step(ctx, "build_context_and_fetch_pr", func(context.Context) (step1Result, error) {
		var contextSummary string
		var prData PRData
		var contextErr, fetchErr error

		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			ticketDesc := in.TicketURL
			if ticketDesc == "" {
				ticketDesc = "No ticket URL provided"
			}
			prompt := fmt.Sprintf("Gather comprehensive context for this code review:\n\nPR URL: %s\nTicket URL: %s\n\nTasks:\n1. Fetch the GitHub PR details\n2. Detect ticket platform and fetch ticket details\n3. Analyze the relationship between PR changes and ticket requirements\n4. Identify any misalignments\n\nProvide a structured summary.", in.PRURL, ticketDesc)
			result, err := ContextBuilderAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
			if err != nil {
				contextErr = err
				return
			}
			contextSummary = result.Response
		}()
		go func() {
			defer wg.Done()
			prData, fetchErr = fetchPRNode(ctx, in.PRURL, cfg.GitHubToken)
		}()
		wg.Wait()

		if contextErr != nil {
			return step1Result{}, contextErr
		}
		if fetchErr != nil {
			return step1Result{}, fetchErr
		}
		return step1Result{contextSummary: contextSummary, prData: prData}, nil
	})
	if err != nil {
		return CodeReviewOutput{}, err
	}
	contextSummary, prData := step1.contextSummary, step1.prData

	fileCount := prData.ChangedFiles
	ctx.Logger().Info("Context built", "pr_number", prData.PRNumber, "files", fileCount)
	if fileCount > prSizeWarningThreshold {
		ctx.Logger().Warn("Large PR — per-file parallel reviews will cover all of them", "files", fileCount)
	}

	// ── Step 2: Tech stack detection ────────────────────────────────────────
	ctx.Logger().Info("Step 2/4: Detecting tech stack")
	techStack, err := agnt5.Step(ctx, "detect_tech_stack", func(context.Context) (TechStack, error) {
		return detectTechStackNode(ctx, prData.Files)
	})
	if err != nil {
		return CodeReviewOutput{}, err
	}

	// ── Step 3: Per-file reviews + security review — all in parallel ───────
	// Each file review sees exactly one file's diff. The security review
	// sees all diffs together for cross-file vulnerability detection.
	var reviewableFiles []PRFile
	for _, f := range prData.Files {
		if f.HasPatch {
			reviewableFiles = append(reviewableFiles, f)
		}
	}
	ctx.Logger().Info("Step 3/4: Reviewing files in parallel + security review", "reviewable", len(reviewableFiles), "total", fileCount)

	prSum := prSummary{Title: prData.Title, Description: prData.Description, Repo: prData.Repo}

	type step3Result struct {
		fileReviews    []FileReview
		securityReview SecurityReview
	}
	step3, err := agnt5.Step(ctx, "review_files_and_security", func(context.Context) (step3Result, error) {
		fileReviews := make([]FileReview, len(reviewableFiles))
		fileErrs := make([]error, len(reviewableFiles))
		var securityReview SecurityReview
		var securityErr error

		var wg sync.WaitGroup
		wg.Add(len(reviewableFiles) + 1)
		for i, f := range reviewableFiles {
			go func(i int, f PRFile) {
				defer wg.Done()
				fileReviews[i], fileErrs[i] = reviewFileNode(ctx, model, f, prSum, techStack)
			}(i, f)
		}
		go func() {
			defer wg.Done()
			securityReview, securityErr = securityReviewNode(ctx, model, reviewableFiles, prSum, techStack)
		}()
		wg.Wait()

		for _, e := range fileErrs {
			if e != nil {
				return step3Result{}, e
			}
		}
		if securityErr != nil {
			return step3Result{}, securityErr
		}
		return step3Result{fileReviews: fileReviews, securityReview: securityReview}, nil
	})
	if err != nil {
		return CodeReviewOutput{}, err
	}
	fileReviews, securityReview := step3.fileReviews, step3.securityReview

	severityCounts := map[string]int{"critical": 0, "major": 0, "minor": 0, "nitpick": 0}
	totalFindings := 0
	for _, fr := range fileReviews {
		for _, f := range fr.Findings {
			severityCounts[f.Severity]++
			totalFindings++
		}
	}
	for _, f := range securityReview.Findings {
		severityCounts[f.Severity]++
	}
	ctx.Logger().Info("Reviews complete", "findings", totalFindings, "files", len(fileReviews), "security_risk", securityReview.OverallRisk)

	// ── Step 4: reviewer_agent synthesizes everything into the final report ─
	ctx.Logger().Info("Step 4/4: Reviewer Agent synthesizing final report")

	synthesisMessage := buildSynthesisMessage(prData, contextSummary, techStack, fileReviews, securityReview, severityCounts)
	reportResult, err := ReviewerAgent.Run(ctx, agnt5.AgentInput{Message: synthesisMessage})
	if err != nil {
		return CodeReviewOutput{}, err
	}
	report := reportResult.Response

	reportFile := saveReport(ctx, in.PRURL, in.TicketURL, report, fileReviews, fileCount, securityReview, severityCounts)

	ctx.Logger().Info("Code review workflow complete")
	return CodeReviewOutput{
		Status: "success", PRURL: in.PRURL, TicketURL: in.TicketURL,
		PRNumber: prData.PRNumber, Repo: prData.Repo,
		FilesReviewed: len(fileReviews), TotalFiles: fileCount,
		SecurityRisk: securityReview.OverallRisk, SeverityCounts: severityCounts,
		TechStack: techStack, ContextSummary: contextSummary,
		Report: report, ReportFile: reportFile,
	}, nil
}

func buildSynthesisMessage(pr PRData, contextSummary string, stack TechStack, fileReviews []FileReview, security SecurityReview, severityCounts map[string]int) string {
	var fileFindings strings.Builder
	for _, fr := range fileReviews {
		fmt.Fprintf(&fileFindings, "\n**%s** (%s) — %s\n", fr.Filename, fr.Language, fr.Summary)
		if len(fr.Findings) == 0 {
			fileFindings.WriteString("  - No issues found\n")
		}
		for _, f := range fr.Findings {
			loc := ""
			if f.LineReference != "" {
				loc = " (" + f.LineReference + ")"
			}
			fmt.Fprintf(&fileFindings, "  - [%s] %s: %s -> %s%s\n", strings.ToUpper(f.Severity), f.Category, f.Description, f.Suggestion, loc)
		}
	}

	var secText strings.Builder
	fmt.Fprintf(&secText, "Overall Risk: %s\n%s\n", strings.ToUpper(security.OverallRisk), security.Summary)
	for _, f := range security.Findings {
		loc := ""
		if f.LineReference != "" {
			loc = " (" + f.LineReference + ")"
		}
		fmt.Fprintf(&secText, "  - [%s] %s -> %s%s\n", strings.ToUpper(f.Severity), f.Description, f.Suggestion, loc)
	}

	techText := fmt.Sprintf("Languages: %s\nFrameworks: %s\nTests in PR: %s\nNotes: %s",
		orDefault(strings.Join(stack.Languages, ", "), "unknown"),
		orDefault(strings.Join(stack.Frameworks, ", "), "none"),
		yesNo(stack.TestFilesPresent), stack.Notes)

	prMeta := fmt.Sprintf("Title: %s\nAuthor: %s\nRepo: %s\nPR #: %d\nState: %s\nDescription: %s\nFiles changed: %d (+%d / -%d)",
		pr.Title, pr.Author, pr.Repo, pr.PRNumber, pr.State, truncate(pr.Description, 500), pr.ChangedFiles, pr.Additions, pr.Deletions)

	return fmt.Sprintf(`Synthesize the following code review findings into a final Markdown report.

## PR Metadata
%s

## PR + Ticket Context (from Context Builder Agent)
%s

## Tech Stack
%s

## Per-File Review Findings (%d files reviewed)
Severity summary: %v
%s

## Security Review
%s

Write a complete, professional Markdown report with executive summary, findings grouped by severity, security section, and a clear merge recommendation (APPROVE / REQUEST CHANGES / BLOCK).`,
		prMeta, contextSummary, techText, len(fileReviews), severityCounts, fileFindings.String(), secText.String())
}

var prURLForFilenamePattern = regexp.MustCompile(`^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)`)

// saveReport writes the final report to reports/<owner>_<repo>_pr_<n>_review.md.
// Failures are logged but don't fail the workflow.
func saveReport(ctx *agnt5.Context, prURL, ticketURL, report string, fileReviews []FileReview, totalFiles int, security SecurityReview, severityCounts map[string]int) string {
	match := prURLForFilenamePattern.FindStringSubmatch(prURL)
	if match == nil {
		return ""
	}
	owner, repoName, prNumber := match[1], match[2], match[3]

	if err := os.MkdirAll("reports", 0o755); err != nil {
		ctx.Logger().Warn("Failed to create reports directory", "error", err)
		return ""
	}
	reportPath := filepath.Join("reports", fmt.Sprintf("%s_%s_pr_%s_review.md", owner, repoName, prNumber))

	ticketDisplay := ticketURL
	if ticketDisplay == "" {
		ticketDisplay = "N/A"
	}
	header := fmt.Sprintf("# Code Review Report\n\n**PR**: %s\n**Ticket**: %s\n**Files reviewed**: %d/%d\n**Security risk**: %s\n**Findings**: %v\n\n---\n\n",
		prURL, ticketDisplay, len(fileReviews), totalFiles, strings.ToUpper(security.OverallRisk), severityCounts)

	if err := os.WriteFile(reportPath, []byte(header+report), 0o644); err != nil {
		ctx.Logger().Warn("Failed to save report", "error", err)
		return ""
	}
	ctx.Logger().Info("Report saved", "path", reportPath)
	return reportPath
}

func orDefault(s, fallback string) string {
	if s == "" {
		return fallback
	}
	return s
}

func yesNo(b bool) string {
	if b {
		return "Yes"
	}
	return "No"
}
