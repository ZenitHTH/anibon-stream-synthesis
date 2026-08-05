// anibon-stream-synthesis — OpenCode plugin registration.
// Registers the skills directory and agents directory so OpenCode discovers
// all stream synthesis skills + anibon-chunk-timestamper / anibon-summarizer agents.

import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default async ({ client } = {}) => {
  const pluginSkillsDir = path.resolve(__dirname, '../../skills');
  const pluginAgentsDir = path.resolve(__dirname, '../agents');

  return {
    config: async (config) => {
      // Register skills
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(pluginSkillsDir)) {
        config.skills.paths.push(pluginSkillsDir);
      }

      // Register agents
      config.agents = config.agents || {};
      config.agents.paths = config.agents.paths || [];
      if (!config.agents.paths.includes(pluginAgentsDir)) {
        config.agents.paths.push(pluginAgentsDir);
      }
    }
  };
};
