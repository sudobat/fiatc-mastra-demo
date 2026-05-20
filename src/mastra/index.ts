import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { DuckDBStore } from '@mastra/duckdb';
import { DatasetsLibSQL, ExperimentsLibSQL, SchedulesLibSQL } from '@mastra/libsql';
import { MSSQLStore } from '@mastra/mssql';
import { Observability, MastraStorageExporter, MastraPlatformExporter, SensitiveDataFilter } from '@mastra/observability';
import { weatherWorkflow } from './workflows/weather-workflow';
import { weatherAgent } from './agents/weather-agent';
import { guiaMedicaAgent } from './agents/guia-medica-agent';
import { mastraMonitoringAgent } from './agents/mastra-monitoring-agent';
import { toolCallAppropriatenessScorer, completenessScorer, translationScorer } from './scorers/weather-scorer';
import { MastraEditor } from '@mastra/editor';

function createMssqlStorage() {
  const password = process.env.MSSQL_SA_PASSWORD;
  if (!password) {
    throw new Error(
      'MSSQL_SA_PASSWORD is not set. Add it to .env (see .env.example) so Mastra can connect to SQL Server from docker-compose.',
    );
  }

  return new MSSQLStore({
    id: 'mssql-storage',
    server: process.env.MSSQL_SERVER ?? 'localhost',
    port: Number(process.env.MSSQL_PORT ?? 1433),
    database: process.env.MSSQL_DATABASE ?? 'master',
    user: process.env.MSSQL_USER ?? 'sa',
    password,
    options: {
      encrypt: true,
      trustServerCertificate: true,
    },
  });
}

function createStorage() {
  const libsqlUrl =
    process.env.MASTRA_LIBSQL_URL ?? process.env.MASTRA_DATASETS_DB_URL ?? 'file:./mastra-local.db';
  const observabilityDbPath =
    process.env.MASTRA_OBSERVABILITY_DB_PATH ?? './mastra-observability.duckdb';
  const storage = createMssqlStorage();

  // MSSQL observability is legacy spans-only (no logs/metrics listing for Studio).
  // DuckDB + LibSQL is Mastra's recommended local stack for traces, logs, and metrics.
  const observability = new DuckDBStore({
    id: 'duckdb-observability',
    path: observabilityDbPath,
  }).observability;

  // Add non-MSSQL domains on the same store so MSSQLStore.init() connects the pool
  // before any domain init (wrapping in an outer MastraCompositeStore skips that).
  storage.stores = {
    ...storage.stores,
    observability,
    schedules: new SchedulesLibSQL({ url: libsqlUrl }),
    datasets: new DatasetsLibSQL({ url: libsqlUrl }),
    experiments: new ExperimentsLibSQL({ url: libsqlUrl }),
  };

  return storage;
}

export const mastra = new Mastra({
  workflows: { weatherWorkflow },
  agents: { weatherAgent, guiaMedicaAgent, mastraMonitoringAgent },
  scorers: { toolCallAppropriatenessScorer, completenessScorer, translationScorer },
  storage: createStorage(),
  logger: new PinoLogger({
    name: 'Mastra',
    level: 'info',
  }),
  observability: new Observability({
    configs: {
      default: {
        serviceName: 'mastra',
        exporters: [
          new MastraStorageExporter(), // Persists observability events to Mastra Storage
          new MastraPlatformExporter(), // Sends observability events to Mastra Platform (if MASTRA_PLATFORM_ACCESS_TOKEN is set)
        ],
        spanOutputProcessors: [
          new SensitiveDataFilter(), // Redacts sensitive data like passwords, tokens, keys
        ],
      },
    },
  }),
  editor: new MastraEditor(),
});
