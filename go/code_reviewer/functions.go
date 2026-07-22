// Workflow steps: PR fetch, tech-stack detection, per-file review, and the
// dedicated security review pass.
package main

import (
	"fmt"
	"sort"
	"strings"

	"agnt5.dev/sdk-go/agnt5"
)

func fetchPRNode(ctx *agnt5.Context, prURL, githubToken string) (PRData, error) {
	data, err := fetchPR(ctx, prURL, githubToken)
	if err != nil {
		return PRData{}, err
	}
	ctx.Logger().Info("PR fetched", "pr_number", data.PRNumber, "files", len(data.Files), "additions", data.Additions, "deletions", data.Deletions)
	return data, nil
}

var languageMap = map[string]string{
	".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
	".jsx": "JavaScript/JSX", ".tsx": "TypeScript/TSX", ".java": "Java",
	".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
	".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
	".kt": "Kotlin", ".scala": "Scala", ".sh": "Shell",
	".html": "HTML", ".css": "CSS", ".sql": "SQL", ".r": "R",
}

var frameworkIndicators = map[string]string{
	"django": "Django", "flask": "Flask", "fastapi": "FastAPI",
	"express": "Express.js", "react": "React", "vue": "Vue.js",
	"angular": "Angular", "spring": "Spring Boot", "rails": "Ruby on Rails",
	"laravel": "Laravel", "next": "Next.js", "nuxt": "Nuxt.js",
	"pytest": "pytest", "jest": "Jest", "sqlalchemy": "SQLAlchemy",
	"prisma": "Prisma", "mongoose": "Mongoose", "celery": "Celery",
	"graphql": "GraphQL", "grpc": "gRPC",
}

var configFileSuffixes = []string{
	"requirements.txt", "package.json", "go.mod", "cargo.toml",
	"gemfile", "composer.json", "pom.xml", "build.gradle",
	".env.example", "dockerfile", "docker-compose.yml",
}

// detectTechStackNode detects languages, frameworks, and tech stack from the
// PR's file list.
func detectTechStackNode(ctx *agnt5.Context, files []PRFile) (TechStack, error) {
	languages := map[string]bool{}
	frameworks := map[string]bool{}
	var configFiles []string
	hasTests := false

	for _, f := range files {
		nameLower := strings.ToLower(f.Filename)

		if i := strings.LastIndex(nameLower, "."); i >= 0 {
			if lang, ok := languageMap["."+nameLower[i+1:]]; ok {
				languages[lang] = true
			}
		}

		if strings.Contains(nameLower, "test") || strings.Contains(nameLower, "spec") ||
			strings.Contains(nameLower, "_test.") || strings.Contains(nameLower, ".test.") {
			hasTests = true
		}

		for _, suffix := range configFileSuffixes {
			if strings.HasSuffix(nameLower, suffix) {
				configFiles = append(configFiles, f.Filename)
				break
			}
		}

		content := nameLower + " " + strings.ToLower(f.Patch)
		for indicator, framework := range frameworkIndicators {
			if strings.Contains(content, indicator) {
				frameworks[framework] = true
			}
		}
	}

	var notes []string
	if !hasTests {
		notes = append(notes, "No test files detected in this PR")
	}
	if len(files) > 20 {
		notes = append(notes, fmt.Sprintf("Large PR: %d files changed", len(files)))
	}
	notesText := "Standard PR size"
	if len(notes) > 0 {
		notesText = strings.Join(notes, "; ")
	}

	stack := TechStack{
		Languages:        sortedKeys(languages),
		Frameworks:       sortedKeys(frameworks),
		TestFilesPresent: hasTests,
		ConfigFiles:      configFiles,
		Notes:            notesText,
	}
	ctx.Logger().Info("Tech stack detected", "languages", stack.Languages, "frameworks", stack.Frameworks)
	return stack, nil
}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

type prSummary struct {
	Title       string
	Description string
	Repo        string
}

// reviewFileNode reviews a single file's diff and returns structured
// findings, using the prompt-for-JSON structured-output helper (see
// utils.go) since GenerateRequest has no response_format field.
func reviewFileNode(ctx *agnt5.Context, model agnt5.LanguageModel, file PRFile, pr prSummary, stack TechStack) (FileReview, error) {
	if file.Patch == "" {
		ctx.Logger().Info("Skipping file — no diff available", "filename", file.Filename)
		return FileReview{
			Filename: file.Filename, Language: "unknown",
			Findings: []Finding{},
			Summary:  "No diff available for this file — binary or renamed file.",
		}, nil
	}

	techStr := fmt.Sprintf("Languages: %s | Frameworks: %s", strings.Join(stack.Languages, ", "), strings.Join(stack.Frameworks, ", "))
	userPrompt := fmt.Sprintf(`Review this file change in the context of the pull request.

PR Title: %s
PR Description: %s
Tech Stack: %s

File: %s
Status: %s (+%d -%d lines)

Diff:
%s

Return a structured review with findings (empty list if no issues) and a summary.`,
		pr.Title, truncate(pr.Description, 500), techStr,
		file.Filename, file.Status, file.Additions, file.Deletions, file.Patch)

	review, err := generateStructured[FileReview](ctx, model, fileReviewerSystemPrompt, userPrompt)
	if err != nil {
		ctx.Logger().Warn("No structured output for file, using empty review", "filename", file.Filename, "error", err)
		return FileReview{
			Filename: file.Filename, Language: "unknown",
			Findings: []Finding{},
			Summary:  "Structured output unavailable for this file.",
		}, nil
	}
	review.Filename = file.Filename
	ctx.Logger().Info("File reviewed", "filename", file.Filename, "findings", len(review.Findings))
	return review, nil
}

// securityReviewNode runs a dedicated security review pass across all
// changed files together (cross-file vulnerability detection).
func securityReviewNode(ctx *agnt5.Context, model agnt5.LanguageModel, files []PRFile, pr prSummary, stack TechStack) (SecurityReview, error) {
	var reviewable []PRFile
	for _, f := range files {
		if f.Patch != "" {
			reviewable = append(reviewable, f)
		}
	}
	if len(reviewable) == 0 {
		return SecurityReview{Findings: []Finding{}, OverallRisk: "low", Summary: "No diffs available to review."}, nil
	}

	const maxFiles = 15 // cap to avoid token limits
	if len(reviewable) > maxFiles {
		reviewable = reviewable[:maxFiles]
	}

	var diffSections []string
	for _, f := range reviewable {
		diffSections = append(diffSections, fmt.Sprintf("### %s (+%d -%d)\n```\n%s\n```", f.Filename, f.Additions, f.Deletions, f.Patch))
	}

	techStr := fmt.Sprintf("Languages: %s | Frameworks: %s", strings.Join(stack.Languages, ", "), strings.Join(stack.Frameworks, ", "))
	userPrompt := fmt.Sprintf(`Perform a security review of this pull request.

PR Title: %s
Repo: %s
Tech Stack: %s

Changed Files and Diffs:
%s

Focus exclusively on security. Return findings (empty list if no security issues) with overall_risk and summary.`,
		pr.Title, pr.Repo, techStr, strings.Join(diffSections, "\n\n"))

	review, err := generateStructured[SecurityReview](ctx, model, securityReviewerSystemPrompt, userPrompt)
	if err != nil {
		ctx.Logger().Warn("No structured output for security review, using empty result", "error", err)
		return SecurityReview{Findings: []Finding{}, OverallRisk: "low", Summary: "Structured output unavailable for security review."}, nil
	}
	ctx.Logger().Info("Security review done", "findings", len(review.Findings), "risk", review.OverallRisk)
	return review, nil
}
