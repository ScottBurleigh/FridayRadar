/**
 * Matchup collapsed GUID / St. vs Saint / city-alias ids onto these keys.
 * Hudl TSV school_id values use the Scout/payload form; look up FridayRadar
 * schools through this map. Never invent a school from a name alone.
 */
const CANONICAL_SCHOOL_ID: Record<string, string> = {
  "fl-fort-lauderdale-st-thomas-aquinas": "fl-fort-lauderdale-saint-thomas-aquinas",
  "fl-na-carol-city-high-school": "fl-opa-locka-miami-carol-city",
  "fl-na-chaminade-madonna-college-preparatory-school": "fl-hollywood-chaminade-madonna",
  "ca-na-linda-esperanza-marquez-high-school": "ca-huntington-park-marquez",
  "ma-na-saint-john-s-prep": "ma-danvers-st-john-s-prep",
  "va-na-benedictine-college-prep": "va-richmond-benedictine",
  "nv-na-mater-academy-east-las-vegas": "nv-las-vegas-mater-academy-east",
  "al-na-mcgill-toolen-catholic-high-school": "al-mobile-mcgill-toolen",
  "mi-na-saint-mary-s-preparatory-school": "mi-orchard-lake-orchard-lake-st-mary-s",
  // NOTE: "tx-na-the-woodlands-college-park-high-school" was once aliased onto
  // tx-the-woodlands-college-park. That was wrong — ESPN files The Woodlands HS
  // recruits under College Park's name, but they are two separate schools in
  // the same town (MaxPreps a9887370… vs 06029cb1…). The record is now stored
  // with its real identity as tx-the-woodlands-the-woodlands; do not re-add it.
  "eur-na-nfl-academy": "en-london-nfl-academy",
  "tx-arlington-summit-high-school": "tx-arlington-mansfield-summit",
  "oh-warren-warren-g-harding-high-school": "oh-warren-harding",
  "tx-southlake-carroll-high-school": "tx-southlake-southlake-carroll",
  "fl-fort-lauderdale-american-heritage": "fl-plantation-american-heritage",
  "fl-windemere-first-academy": "fl-orlando-the-first-academy",
  "nj-ramsey-don-bosco-high-school": "nj-ramsey-don-bosco-prep",
  "al-montgomery-the-montgomery-academy": "al-montgomery-montgomery-academy",
  "tx-houston-c-e-king-high-school": "tx-houston-c-e-king",
  "ga-grayson-grayson": "ga-loganville-grayson",
  "md-baltimore-saint-frances-academy": "md-baltimore-st-frances-academy",
  "va-springfield-saint-james": "va-springfield-the-st-james",
  "nj-jersey-city-saint-peters-prep": "nj-jersey-city-st-peter-s-prep",
  "il-east-saint-louis-east-saint-louis": "il-east-st-louis-east-st-louis",
  "ca-bellflower-saint-john-bosco": "ca-bellflower-st-john-bosco",
  "fl-jacksonville-bolles-school": "fl-jacksonville-the-bolles-school",
  // Hudl TSV school_id aliases (verified fan.hudl.com team URLs). Unique names.
  "dc-washington-saint-johns-college": "dc-washington-st-john-s-college",
  "nj-montvale-saint-joseph-regional": "nj-montvale-st-joseph-regional",
  // Do NOT alias ca-san-mateo-junipero-serra onto Gardena Serra — different cities.
};

export function canonicalSchoolId(id: string | undefined | null): string {
  if (!id) return "";
  return CANONICAL_SCHOOL_ID[id] || id;
}
