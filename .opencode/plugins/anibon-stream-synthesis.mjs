// anibon-stream-synthesis — OpenCode plugin registration.
// Registers the skills directory so OpenCode discovers all stream synthesis skills.

import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default async ({ client } = {}) => {
  const pluginSkillsDir = path.resolve(__dirname, '../../skills');

  return {
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(pluginSkillsDir)) {
        config.skills.paths.push(pluginSkillsDir);
      }
    }
  };
};
