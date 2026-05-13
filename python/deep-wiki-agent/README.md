# AGNT5 DeepWiki Investigator

Durable investigator agent that uses the DeepWiki MCP server to research repos, drafts a brief, pauses for human review, and saves the result.

```bash
echo 'OPENAI_API_KEY="sk-..."' > .env   # or AGNT5_MOCK_MODE=1
agnt5 dev
agnt5 run investigate_with_review --input '{"question": "Should we migrate from Redis to Valkey?"}'
```

Full walkthrough: <https://docs.agnt5.com/docs/templates/deep-wiki-agent>.
