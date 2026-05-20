import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { GUIA_MEDICA_INSTRUCTIONS } from '../guia-medica/prompts';
import { guiaMedicaTools } from '../guia-medica/tools';

export const guiaMedicaAgent = new Agent({
  id: 'guia-medica-agent',
  name: 'Guía Médica FIATC',
  instructions: GUIA_MEDICA_INSTRUCTIONS,
  model: process.env.GUIA_MEDICA_MODEL ?? 'anthropic/claude-sonnet-4-6',
  tools: guiaMedicaTools,
  memory: new Memory(),
});
