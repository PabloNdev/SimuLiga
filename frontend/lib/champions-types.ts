import type { Mode, Team } from "@/lib/types";

export interface ChampionsTeam extends Team {
  country: string;
  pot: number | null;
}

export interface ChampionsStanding {
  position: number;
  team: ChampionsTeam;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  away_goals: number;
  wins: number;
  away_wins: number;
  points: number;
}

export interface ChampionsModel {
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

export interface ChampionsSeasonPayload {
  competition: string;
  season: string;
  target_season: string | null;
  phase: string;
  source: string;
  demo: boolean;
  fallback: boolean;
  data_note: string | null;
  updated_at: string;
  data_version: string;
  current_matchday: number;
  total_matchdays: number;
  played_matches: number;
  pending_matches: number;
  teams: ChampionsTeam[];
  standings: ChampionsStanding[];
  model: ChampionsModel;
  tiebreak_rules: string[];
  qualification_zones: {
    direct: [number, number];
    playoff: [number, number];
    eliminated: [number, number];
  };
}

export interface ChampionsProjectionTeam {
  team: ChampionsTeam;
  expected_points: number;
  points_std: number;
  median_points: number;
  p10_points: number;
  p90_points: number;
  expected_position: number;
  most_likely_position: number;
  top8_probability: number;
  playoff_probability: number;
  eliminated_probability: number;
  playoff_win_probability: number;
  round_of_16_probability: number;
  position_probabilities: number[];
  opponent_probabilities: Record<string, number>;
  points_histogram: number[];
}

export interface ChampionsMatchPrediction {
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

export interface ChampionsBracketEntry {
  better_slot: number;
  worse_slot: number;
  better_team: ChampionsTeam | null;
  better_probability: number;
  worse_team: ChampionsTeam | null;
  worse_probability: number;
}

export interface ChampionsMatchup {
  better_id: string;
  worse_id: string;
  probability: number;
  better_team: ChampionsTeam | null;
  worse_team: ChampionsTeam | null;
}

export interface ChampionsPlayoff {
  bracket: ChampionsBracketEntry[];
  advance_probabilities: Record<string, number>;
  opponent_probabilities: Record<string, Record<string, number>>;
  matchups: ChampionsMatchup[];
}

export interface ChampionsProjectionPayload {
  mode: Mode;
  n_sims: number;
  seed: number | null;
  elapsed_seconds: number;
  goals_available: boolean;
  data_version: string;
  source: string;
  demo: boolean;
  fallback: boolean;
  data_note: string | null;
  base_standings: ChampionsStanding[];
  teams: ChampionsProjectionTeam[];
  match_predictions: ChampionsMatchPrediction[];
  playoff: ChampionsPlayoff;
}

export interface ChampionsMatchItem {
  id: string;
  matchday: number;
  kickoff: string | null;
  home: ChampionsTeam;
  away: ChampionsTeam;
  status: "played" | "pending";
  score: [number | null, number | null] | null;
  outcome: "H" | "D" | "A" | null;
  home_probability: number | null;
  draw_probability: number | null;
  away_probability: number | null;
  most_likely_score: [number, number] | null;
}

export interface ChampionsMatchesPayload {
  source: string;
  demo: boolean;
  fallback: boolean;
  data_note: string | null;
  data_version: string;
  mode: Mode;
  current_matchday: number;
  matches: ChampionsMatchItem[];
}

export interface ChampionsEloTeam extends ChampionsTeam {
  position: number;
  start_elo: number;
  delta: number;
  played: number;
}

export interface ChampionsEloPayload {
  season: string;
  source: string;
  demo: boolean;
  fallback: boolean;
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
  teams: ChampionsEloTeam[];
  history: {
    seasons: string[];
    series: { team_id: string; values: (number | null)[] }[];
    origin: number;
  };
  verification: Record<string, unknown> & {
    available: boolean;
    previous_season?: string;
    matches_total?: number;
    matches_applied?: number;
    matches_without_score?: number;
    teams_total?: number;
    teams_resolved?: number;
    seed_source?: string;
    sources?: string[];
    fallback?: boolean;
    current_matches_total?: number;
    current_matches_played?: number;
    history_seasons?: number;
    history_start?: string;
    history_end?: string;
    history_seasons_loaded?: string[];
    history_complete?: boolean;
    season_regression?: number;
    history_matches_total?: number;
    history_matches_applied?: number;
    history_matches_without_score?: number;
    clubelo_prior?: boolean;
    clubelo_prior_weight?: number;
    clubelo_source?: string;
    clubelo_dates?: string[];
    clubelo_teams_matched?: number;
    params?: {
      home_advantage?: number;
      nu?: number;
      validation?: {
        matches: number;
        accuracy: number;
        log_loss: number;
        brier: number;
      };
    };
  };
  timeline: {
    dates: string[];
    series: { team_id: string; values: (number | null)[] }[];
  };
}

export interface ChampionsValidationPayload {
  status: string;
  message: string;
  metrics: {
    matches: number;
    accuracy: number;
    log_loss: number;
    brier: number;
    train_home_advantage?: number;
    train_nu?: number;
  } | null;
  model: ChampionsModel;
  data: {
    source: string;
    data_version: string;
    demo: boolean;
    fallback: boolean;
    teams: number;
    matches: number;
    played: number;
    seed_source?: string;
    previous_season?: string;
    previous_matches?: number;
    previous_applied?: number;
  };
}
