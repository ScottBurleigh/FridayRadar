export type RatingSource =
  | "247sports"
  | "247sports_composite"
  | "on3_rivals"
  | "on3_industry"
  | "espn";

export type MaxPrepsRef = {
  schoolId: string;
  canonicalUrl: string;
  formattedName: string | null;
  footballUrl?: string | null;
  scheduleUrl?: string | null;
};

export type StrengthBreakdown = {
  talentScore?: number | null;
  talentMax?: number | null;
  talentMaxName?: string | null;
  talentNorm?: number | null;
  on3Rank?: number | null;
  on3Rating?: number | null;
  on3Min?: number | null;
  on3Max?: number | null;
  on3Norm?: number | null;
  maxprepsRank?: number | null;
  maxprepsNorm?: number | null;
  rankingNorm?: number | null;
  blended?: number | null;
  dctfRank?: number | null;
  bonus?: number | null;
  teamStrength?: number | null;
};

export type School = {
  id: string;
  name: string;
  name_normalized: string;
  aliases: string[];
  mascot: string | null;
  city: string;
  state: string;
  zip: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  type: string | null;
  maxpreps: MaxPrepsRef | null;
  ids_247: { high_school_id: string | null };
  /** Scout precomputed 2027+ talent. Rankings prefer this over summing imported rows. */
  talentScore?: number | null;
  recruitCount?: number | null;
  stars5?: number | null;
  stars4?: number | null;
  stars3?: number | null;
  /** false = Matchup opponent with no Scout roster (one-sided talent). */
  mapped?: boolean;
  /** 0–100 talent share blended with On3 / MaxPreps ranks, plus DCTF 6A bonus in Texas. */
  teamStrength?: number | null;
  /** Public fan.hudl.com boys-varsity-football page when verified. Never invented. */
  hudlTeamUrl?: string | null;
  on3?: {
    rank: number;
    rating: number | null;
    orgKey?: string | number | null;
  } | null;
  maxprepsNational?: { rank: number } | null;
  dctf?: { rank: number; board?: string | null } | null;
  strengthBreakdown?: StrengthBreakdown | null;
  sos?: number | null;
  sosGames?: number | null;
  sosLabel?: "tough" | "average" | "light" | null;
  scheduleGames?: number | null;
};

export type Player = {
  id: string;
  full_name: string;
  class_year: number;
  position: string | null;
  height: string | null;
  weight: number | null;
  hometown_city: string | null;
  hometown_state: string | null;
  high_school_id: string;
  college_commit: string | null;
  source_ids: {
    "247sports_player_id"?: string;
    on3_rivals_id?: string;
    espn_id?: string;
    hudl?: string;
  };
  /** External profiles. Hudl is set only from the verified payload — never invented. */
  profile_urls?: {
    "247sports_composite"?: string;
    on3_rivals?: string;
    espn?: string;
    hudl?: string;
  };
};

export type Rating = {
  player_id: string;
  source: RatingSource;
  class_year: number;
  as_of: string;
  national_rank: number | null;
  position_rank: number | null;
  state_rank: number | null;
  stars: number | null;
  rating: number | null;
  position: string | null;
  high_school_name_raw: string | null;
  profile_url: string | null;
};

export type GameVenue = {
  city: string | null;
  state: string | null;
  zip: string | null;
  name: string | null;
  source: "home_school" | "contest_location" | null;
};

export type Game = {
  id: string;
  season: string;
  kickoff: string | null;
  home_school_id: string;
  away_school_id: string;
  home_score: number | null;
  away_score: number | null;
  is_gow: boolean;
  game_url: string | null;
  /** Venue city (where the game is played), not either roster's school. */
  city: string | null;
  /** Venue state. Missing ⇒ unmatched for the state filter. */
  state: string | null;
  /** Venue zip. Used with lat/lng for the ~25-mile radius filter. */
  zip: string | null;
  lat: number | null;
  lng: number | null;
  venue?: GameVenue | null;
  two_sided_talent?: number | null;
  is_time_tba: boolean;
  /** 0 = home, 1 = away, 2 = neutral site. */
  home_away_type: 0 | 1 | 2;
};

export type SourceStatus = {
  id: string;
  label: string;
  status: "live" | "live-partial" | "blocked" | "sample";
  detail: string;
  counts?: Record<string, number>;
};

export type DatasetMeta = {
  generated_at: string;
  as_of: string;
  min_class_year: number;
  sources: SourceStatus[];
  notes: string[];
  matchup_week?: { start: string; end: string };
};

export type FridayRadarDataset = {
  meta: DatasetMeta;
  schools: School[];
  players: Player[];
  ratings: Rating[];
  games: Game[];
  schedules?: Record<string, SchoolSchedule>;
};

export type SosLabel = "tough" | "average" | "light";

export type ToughnessIcon =
  | "much_harder"
  | "harder"
  | "even"
  | "easier"
  | "much_easier"
  | "unknown";

export type ScheduleOpponent = {
  name: string;
  city: string | null;
  state: string | null;
  maxprepsId: string | null;
  siteId: string | null;
  teamStrength: number | null;
};

export type ScheduleGame = {
  contestId: string | null;
  date: string | null;
  kickoff: string | null;
  homeAway: "home" | "away" | "neutral";
  location: string | null;
  opponent: ScheduleOpponent;
  result: string | null;
  score: number | null;
  oppScore: number | null;
  maxprepsGameUrl: string | null;
  toughnessIcon: ToughnessIcon;
};

export type SchoolSchedule = {
  schoolId: string;
  season: string;
  teamStrength: number | null;
  scheduleUrl: string | null;
  sos: number | null;
  sosGames: number;
  games: ScheduleGame[];
};

export type SchoolRankingRow = {
  rank: number;
  school: School;
  recruitCount: number;
  stars5: number;
  stars4: number;
  stars3: number;
  talentScore: number;
  teamStrength: number | null;
  sos: number | null;
  sosLabel: "tough" | "average" | "light" | null;
};

export type RatedPlayer = Player & {
  compositeStars: number | null;
  badgeStars: number;
  points: number;
  ratingsBySource: Partial<Record<RatingSource, Rating>>;
};

export type ProfileLink = {
  label: "247" | "On3" | "ESPN" | "Hudl";
  href: string;
};

/** Compact roster row for the rankings accordion — not the full school page. */
export type InlineRecruit = {
  id: string;
  name: string;
  position: string | null;
  classYear: number;
  stars247: number | null;
  starsOn3: number | null;
  starsEspn: number | null;
  profileUrl: string | null;
  profileUrls: ProfileLink[];
};
