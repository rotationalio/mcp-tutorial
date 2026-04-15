// MongoDB: narrative / wide event result documents from Hugging Face CSV mirrors.

const dbName = 'olympics';
const olympics = db.getSiblingDB(dbName);

olympics.createCollection('olympic_athlete_biography');
olympics.createCollection('olympic_event_results');

// mongosh: each entry is the index key pattern (not { key: { ... } }).
olympics.olympic_athlete_biography.createIndexes([
  { athlete_id: 1 },
  { country_noc: 1 },
]);

olympics.olympic_event_results.createIndexes([
  { result_id: 1 },
  { edition_id: 1 },
  { sport: 1, event_title: 1 },
]);
