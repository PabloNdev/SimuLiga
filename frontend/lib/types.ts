export type Mode = "score" | "1x2";
export type Outcome = "H" | "D" | "A";

export interface Team {
  id: string;
  name: string;
  short_name: string;
  color: string;
  elo: number;
}

export interface Standing {
  position: number;
  team: Team;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}

export interface ModelInfo {
  davidson: {
    home_advantage: number;
    nu: number;
    elo_scale: number;
  };
  scoreline: {
    home_base: number;
    away_base: number;
    elo_slope: number;
    home_advantage: number;
    rho: number;
    max_goals: number;
  };
}

export interface EloTeam {
  position: number;
  id: string;
  name: string;
  short_name: string;
  color: string;
  elo: number;
  start_elo: number;
  delta: number;
  played: number;
}

export interface EloHistorySeries {
  team_id: string;
  values: (number | null)[];
}

export interface EloHistory {
  seasons: string[];
  series: EloHistorySeries[];
  origin: number;
  promoted_baseline_2025?: number;
}

export interface EloVerification {
  available: boolean;
  previous_season?: string;
  matches_total?: number;
  matches_applied?: number;
  matches_without_score?: number;
  matches_filled_from_football_data?: number;
  matches_missing?: number;
  matches_unresolved?: number;
  teams_total?: number;
  teams_resolved?: number;
  sources?: string[];
  baseline_label?: string;
  baseline?: Record<string, number | null>;
  played_previous_season?: Record<string, boolean>;
  promoted_baseline_2025?: number;
  promoted_baseline_2026?: number;
}

export interface EloTimelineSeries {
  team_id: string;
  values: (number | null)[];
}

export interface EloTimeline {
  dates: string[];
  series: EloTimelineSeries[];
}

export interface EloPayload {
  season: string;
  source: string;
  demo: boolean;
  data_note: string | null;
  updated_at: string;
  data_version: string;
  current_matchday: number;
  total_matchdays: number;
  played_matches: number;
  params: {
    k: number;
    home_advantage: number;
    elo_scale: number;
    start_rating: number;
  };
  teams: EloTeam[];
  history: EloHistory;
  verification: EloVerification;
  timeline: EloTimeline;
}

export interface SeasonPayload {
  competition: string;
  season: string;
  source: string;
  demo: boolean;
  data_note: string | null;
  updated_at: string;
  data_version: string;
  current_matchday: number;
  total_matchdays: number;
  played_matches: number;
  pending_matches: number;
  teams: Team[];
  standings: Standing[];
  model: ModelInfo;
  tiebreak_rules: string[];
}

export interface TeamProjection {
  team: Team;
  expected_points: number;
  points_std: number;
  median_points: number;
  p10_points: number;
  p90_points: number;
  expected_position: number;
  most_likely_position: number;
  champion_probability: number;
  top4_probability: number;
  relegation_probability: number;
  position_probabilities: number[];
  points_histogram: number[];
}

export interface MatchPrediction {
  match_id: string;
  matchday: number;
  home_id: string;
  away_id: string;
  home_probability: number;
  draw_probability: number;
  away_probability: number;
  most_likely_score: [number, number] | null;
  most_likely_score_probability: number | null;
}

export interface ProjectionPayload {
  mode: Mode;
  n_sims: number;
  seed: number | null;
  elapsed_seconds: number;
  goals_available: boolean;
  start_matchday: number | null;
  base_played_matches: number;
  base_standings: Standing[];
  data_version: string;
  source: string;
  teams: TeamProjection[];
  match_predictions: MatchPrediction[];
}

export interface MatchItem {
  id: string;
  matchday: number;
  kickoff: string | null;
  home: Team;
  away: Team;
  status: "played" | "pending";
  score: [number | null, number | null] | null;
  outcome: Outcome | null;
  home_probability: number | null;
  draw_probability: number | null;
  away_probability: number | null;
  most_likely_score: [number, number] | null;
}

export interface MatchesPayload {
  source: string;
  data_version: string;
  mode: Mode;
  current_matchday: number;
  matches: MatchItem[];
}

export interface ScenarioRequest {
  mode: Mode;
  sims: number;
  start_matchday?: number | null;
  seed?: number | null;
  elo_delta?: Record<string, number>;
  forced_results?: Record<string, Outcome>;
  forced_scores?: Record<string, [number, number]>;
  home_advantage?: number;
  nu?: number;
  rho?: number;
}

export interface JobCreated {
  job_id: string;
  status: string;
}

export interface JobPayload {
  job_id: string;
  status: "running" | "done" | "error";
  result: ProjectionPayload | null;
  error: string | null;
  progress: number;
  completed_sims: number;
  elapsed_seconds: number;
}

export interface ValidationPayload {
  status: string;
  message: string;
  metrics: {
    season: number;
    home_advantage: number;
    nu: number;
    matches: number;
    accuracy: number;
    log_loss: number;
    brier: number;
  } | null;
  calibration: {
    trained_on: number[] | null;
    fit_on?: number[] | null;
    generated_at: string | null;
  };
  model: ModelInfo;
  data: {
    source: string;
    data_version: string;
    teams: number;
    matches: number;
    played: number;
  };
}
