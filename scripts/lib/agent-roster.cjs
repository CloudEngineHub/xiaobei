// Read legacy input during upgrades; persist canonical keyed entries whenever present.
function listAgents(config) {
  const agents = config.agents ?? {};
  if (agents.entries && typeof agents.entries === "object" && !Array.isArray(agents.entries)) {
    return Object.entries(agents.entries).map(([id, entry]) => ({ ...entry, id }));
  }
  return Array.isArray(agents.list) ? agents.list : [];
}
function getAgent(config, id) {
  return listAgents(config).find((entry) => entry.id === id);
}
function setAgent(config, id, value) {
  config.agents ??= {};
  if (
    config.agents.entries &&
    typeof config.agents.entries === "object" &&
    !Array.isArray(config.agents.entries)
  ) {
    const { id: _id, ...entry } = value;
    config.agents.entries[id] = entry;
  } else if (Array.isArray(config.agents.list)) {
    const index = config.agents.list.findIndex((entry) => entry.id === id);
    const entry = { ...value, id };
    if (index < 0) config.agents.list.push(entry);
    else config.agents.list[index] = entry;
  } else {
    const { id: _id, ...entry } = value;
    config.agents.entries = { [id]: entry };
  }
}
module.exports = { listAgents, getAgent, setAgent };
