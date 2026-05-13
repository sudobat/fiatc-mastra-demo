import { MCPClient, type MastraMCPServerDefinition } from '@mastra/mcp';

function buildSqlServerDsnForDbhub(): string {
  const password = process.env.MSSQL_SA_PASSWORD;
  if (!password) {
    throw new Error(
      'MSSQL_SA_PASSWORD is not set. DBHub stdio mode needs a SQL Server DSN. Set MSSQL_* in .env (see .env.example), or set DBHUB_MCP_URL to a running DBHub HTTP endpoint.',
    );
  }
  const user = encodeURIComponent(process.env.MSSQL_USER ?? 'sa');
  const pass = encodeURIComponent(password);
  const server = process.env.MSSQL_SERVER ?? 'localhost';
  const port = process.env.MSSQL_PORT ?? '1433';
  const database = encodeURIComponent(process.env.MSSQL_DATABASE ?? 'master');
  return `sqlserver://${user}:${pass}@${server}:${port}/${database}?sslmode=require`;
}

function spawnEnv(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined),
  );
}

function getDbhubServerDefinition(): MastraMCPServerDefinition {
  const mcpUrl = process.env.DBHUB_MCP_URL?.trim();
  if (mcpUrl) {
    return { url: new URL(mcpUrl) };
  }
  const dsn = buildSqlServerDsnForDbhub();
  return {
    command: 'npx',
    args: ['-y', '@bytebase/dbhub@latest', '--transport', 'stdio', '--dsn', dsn],
    env: spawnEnv(),
  };
}

/**
 * MCP client for [DBHub](https://dbhub.ai/) (SQL Server via stdio + `MSSQL_*`, or HTTP via `DBHUB_MCP_URL`).
 * Use with agents: `tools: await dbhubMcpClient.listTools()` — see [Mastra MCP docs](https://mastra.ai/docs/mcp/overview).
 */
export const dbhubMcpClient = new MCPClient({
  id: 'dbhub-mcp-client',
  servers: {
    dbhub: getDbhubServerDefinition(),
  },
});
