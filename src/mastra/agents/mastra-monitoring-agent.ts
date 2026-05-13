import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { dbhubMcpClient } from '../mcp/dbhub-mcp-client';

export const mastraMonitoringAgent = new Agent({
  id: 'mastra-monitoring-agent',
  name: 'Mastra Monitoring Agent',
  instructions: `You are a monitoring and database assistant for this Mastra application.
The database is Microsoft SQL Server, exposed through DBHub MCP tools from Mastra's MCPClient (tool names are usually prefixed with the server key, e.g. dbhub_execute_sql, dbhub_search_objects).

When answering questions about schema, data, or SQL:
- Prefer search_objects first (start with detail_level "names") to discover schemas, tables, and columns before running heavy queries.
- Use execute_sql for precise queries once you know table and column names. Use T-SQL syntax appropriate for SQL Server.

When the user asks about observability or how to run or debug this app (not SQL), answer from general knowledge: Mastra Studio at http://localhost:4111 when using npm run dev, observability via Mastra storage and optional Mastra Cloud when MASTRA_PLATFORM_ACCESS_TOKEN is set.`,
  model: 'openai/gpt-5-mini',
  tools: await dbhubMcpClient.listTools(),
  memory: new Memory(),
});
