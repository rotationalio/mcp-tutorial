// MongoDB: narrative / wide event result documents from Hugging Face CSV mirrors.

const dbName = 'olympics';
const olympics = db.getSiblingDB(dbName);

olympics.createCollection('olympic_athlete_biography');
olympics.createCollection('olympic_event_results');

olympics.olympic_athlete_biography.createIndexes([
  { key: { athlete_id: 1 } },
  { key: { country_noc: 1 } },
]);

olympics.olympic_event_results.createIndexes([
  { key: { result_id: 1 } },
  { key: { edition_id: 1 } },
  { key: { sport: 1, event_title: 1 } },
]);
