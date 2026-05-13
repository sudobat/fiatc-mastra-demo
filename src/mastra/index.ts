import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { MSSQLStore } from '@mastra/mssql';
import { Observability, MastraStorageExporter, MastraPlatformExporter, SensitiveDataFilter } from '@mastra/observability';
import { weatherWorkflow } from './workflows/weather-workflow';
import { weatherAgent } from './agents/weather-agent';
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

export const mastra = new Mastra({
  workflows: { weatherWorkflow },
  agents: { weatherAgent, mastraMonitoringAgent },
  scorers: { toolCallAppropriatenessScorer, completenessScorer, translationScorer },
  storage: createMssqlStorage(),
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
