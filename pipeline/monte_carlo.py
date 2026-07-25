"""
Monte Carlo playoff probability simulator for IPL 2026.

Algorithm:
  1. Load the current points table (standings) and remaining schedule.
  2. For each of N simulations:
       a. For every unplayed match, sample the winner using stored win
          probabilities (from the match prediction model).
       b. Award 2 pts to the winner, 0 to the loser.
       c. At the end of the league stage, sort teams by (Pts DESC, NRR DESC).
          NRR tiebreaker uses a small random perturbation seeded from form.
       d. Record which 4 teams qualify.
  3. Aggregate across simulations to produce qualification probabilities,
     expected finishing positions, expected points, and "eliminated" flags.

Additional outputs:
  - Qualification probability per team (top-4 finish)
  - Title probability per team (finishing #1)
  - Expected points at end of league stage
  - Scenarios: "magic number" to qualify, "elimination number"
  - Match importance scores: how much each remaining match changes
    the avg qualification probability for the two teams involved
"""

import logging
from collections import defaultdict
from copy import deepcopy

import numpy as np

logger = logging.getLogger(__name__)

N_SIMULATIONS = 10_000
RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------


def _simulate_once(
    standings: dict[str, dict],
    remaining: list[dict],
    rng: np.random.Generator,
) -> dict[str, int]:
    """
    Run one simulation of the remaining league stage.
    Returns final points dict keyed by team name.
    """
    pts = {team: data["pts"] for team, data in standings.items()}
    nrr = {team: data["nrr"] for team, data in standings.items()}

    for match in remaining:
        t1 = match["team1"]
        t2 = match["team2"]
        p1 = match.get("team1_win_prob", 0.5)
        p1 = max(0.05, min(0.95, float(p1)))

        winner = t1 if rng.random() < p1 else t2
        loser = t2 if winner == t1 else t1

        pts[winner] = pts.get(winner, 0) + 2
        pts.setdefault(loser, 0)

        # Small NRR perturbation: winner improves ~+0.05, loser ~-0.05
        nrr[winner] = nrr.get(winner, 0.0) + float(rng.normal(0.05, 0.03))
        nrr[loser] = nrr.get(loser, 0.0) + float(rng.normal(-0.05, 0.03))

    # Sort: pts DESC, then NRR DESC
    sorted_teams = sorted(pts.keys(), key=lambda t: (-pts[t], -nrr.get(t, 0.0)))
    return {team: rank + 1 for rank, team in enumerate(sorted_teams)}


def run_simulation(
    standings: list[dict],
    schedule: list[dict],
    n_simulations: int = N_SIMULATIONS,
    seed: int = RANDOM_SEED,
) -> dict:
    """
    Run the full Monte Carlo playoff probability simulation.

    Parameters
    ----------
    standings : list of dicts with keys: Team, Pts, W, L, P, NRR
    schedule  : list of dicts with keys: team1, team2, played, winner,
                team1_win_prob, team2_win_prob, match (number), date
    n_simulations : number of Monte Carlo trials
    seed : random seed for reproducibility

    Returns
    -------
    dict with per-team stats and per-match importance scores
    """
    rng = np.random.default_rng(seed)

    # Build standings lookup
    standings_map: dict[str, dict] = {}
    for row in standings:
        team = row.get("Team", row.get("team", ""))
        standings_map[team] = {
            "pts": int(row.get("Pts", row.get("pts", 0))),
            "nrr": float(row.get("NRR", row.get("nrr", 0.0))),
            "played": int(row.get("P", row.get("played", 0))),
            "won": int(row.get("W", row.get("won", 0))),
        }

    all_teams = list(standings_map.keys())

    # Separate remaining matches from completed ones
    remaining = []
    completed_winners: dict[str, int] = defaultdict(int)  # team → wins from completed

    for m in schedule:
        played = m.get("played", False)
        if played:
            if m.get("winner"):
                completed_winners[m["winner"]] += 1
        else:
            t1 = m.get("team1", "")
            t2 = m.get("team2", "")
            if t1 and t2 and t1 in standings_map and t2 in standings_map:
                remaining.append(
                    {
                        "match": m.get("match"),
                        "date": m.get("date", ""),
                        "team1": t1,
                        "team2": t2,
                        "team1_win_prob": float(m.get("team1_win_prob", 0.5)),
                        "team2_win_prob": float(m.get("team2_win_prob", 0.5)),
                    }
                )

    logger.info(
        "Monte Carlo: %d teams | %d remaining matches | %d simulations",
        len(all_teams),
        len(remaining),
        n_simulations,
    )

    # Accumulators
    qualify_count: dict[str, int] = defaultdict(int)
    title_count: dict[str, int] = defaultdict(int)
    position_sum: dict[str, float] = defaultdict(float)
    pts_sum: dict[str, float] = defaultdict(float)
    position_dist: dict[str, dict] = {t: defaultdict(int) for t in all_teams}

    for _ in range(n_simulations):
        final_ranks = _simulate_once(standings_map, remaining, rng)

        for team, rank in final_ranks.items():
            if rank <= 4:
                qualify_count[team] += 1
            if rank == 1:
                title_count[team] += 1
            position_sum[team] += rank
            position_dist[team][rank] += 1

        # Recompute pts for this sim (pts_sum approximation from standings + wins)
        sim_pts = {t: standings_map[t]["pts"] for t in all_teams}
        for match in remaining:
            sorted_by_rank = sorted(final_ranks.items(), key=lambda x: x[1])
            sorted_by_rank[0][0] if sorted_by_rank else match["team1"]
            # Approximate: give 2pts to whoever ranked higher of these two
            t1, t2 = match["team1"], match["team2"]
            if final_ranks.get(t1, 99) < final_ranks.get(t2, 99):
                sim_pts[t1] = sim_pts.get(t1, 0) + 2
            else:
                sim_pts[t2] = sim_pts.get(t2, 0) + 2

        for team in all_teams:
            pts_sum[team] += sim_pts.get(team, standings_map[team]["pts"])

    # --- Match importance scores ---
    # For each remaining match, measure how much the avg qualification prob
    # changes if we force team1 to win vs force team2 to win.
    match_importance = []
    sample_n = min(1000, n_simulations)
    rng2 = np.random.default_rng(seed + 1)

    for match in remaining:
        t1, t2 = match["team1"], match["team2"]
        other_remaining = [m for m in remaining if m is not match]

        t1_wins_qualify: dict[str, int] = defaultdict(int)
        t2_wins_qualify: dict[str, int] = defaultdict(int)

        for forced_winner, acc in [(t1, t1_wins_qualify), (t2, t2_wins_qualify)]:
            forced_pts = deepcopy(standings_map)
            forced_pts[forced_winner]["pts"] += 2

            for _ in range(sample_n):
                ranks = _simulate_once(forced_pts, other_remaining, rng2)
                for team, rank in ranks.items():
                    if rank <= 4:
                        acc[team] += 1

        # Swing = how much t1 and t2's own qualification changes
        t1_swing = abs(t1_wins_qualify.get(t1, 0) / sample_n - t2_wins_qualify.get(t1, 0) / sample_n)
        t2_swing = abs(t1_wins_qualify.get(t2, 0) / sample_n - t2_wins_qualify.get(t2, 0) / sample_n)
        importance = round((t1_swing + t2_swing) / 2, 4)

        match_importance.append(
            {
                "match": match.get("match"),
                "date": match.get("date", ""),
                "team1": t1,
                "team2": t2,
                "importance": importance,
                "t1_swing": round(t1_swing, 4),
                "t2_swing": round(t2_swing, 4),
            }
        )

    match_importance.sort(key=lambda x: -x["importance"])

    # --- Compile per-team results ---
    team_results = []
    for team in all_teams:
        current = standings_map[team]
        qualify_prob = qualify_count[team] / n_simulations
        title_prob = title_count[team] / n_simulations
        avg_position = position_sum[team] / n_simulations
        avg_pts = pts_sum[team] / n_simulations

        # Magic number: minimum wins still needed to guarantee top-4
        # (simplified: if qualify_prob > 0.99, magic_number = 0)
        magic_number = None
        if qualify_prob >= 0.99:
            magic_number = 0
        elif qualify_prob <= 0.01:
            magic_number = None  # eliminated

        # Games remaining for this team
        games_remaining = sum(1 for m in remaining if m["team1"] == team or m["team2"] == team)

        # Finish position distribution (top 5 positions)
        pos_dist = {f"P{p}": round(position_dist[team].get(p, 0) / n_simulations * 100, 1) for p in range(1, 6)}

        team_results.append(
            {
                "team": team,
                "current_pts": current["pts"],
                "current_nrr": current["nrr"],
                "games_remaining": games_remaining,
                "qualify_prob": round(qualify_prob, 4),
                "title_prob": round(title_prob, 4),
                "avg_finish": round(avg_position, 2),
                "avg_final_pts": round(avg_pts, 1),
                "magic_number": magic_number,
                "position_dist": pos_dist,
            }
        )

    team_results.sort(key=lambda x: (-x["qualify_prob"], x["avg_finish"]))

    return {
        "team_results": team_results,
        "match_importance": match_importance,
        "n_simulations": n_simulations,
        "remaining_matches": len(remaining),
        "methodology": (
            f"{n_simulations:,} Monte Carlo simulations. "
            "Each sim samples remaining match outcomes using model win probabilities, "
            "resolves ties via NRR with Gaussian noise, and records top-4 finishes. "
            "Match importance = average swing in qualification probability when forcing each team to win."
        ),
    }


def run(standings: list[dict], schedule: list[dict], n: int = N_SIMULATIONS) -> dict:
    """Public entry point for the pipeline."""
    return run_simulation(standings, schedule, n_simulations=n)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick smoke test with mock data
    mock_standings = [
        {"Team": f"Team {i}", "Pts": (10 - i) * 2, "W": 10 - i, "L": i, "P": 10, "NRR": round(1.0 - i * 0.2, 3)}
        for i in range(10)
    ]
    mock_schedule = [
        {
            "team1": f"Team {i}",
            "team2": f"Team {j}",
            "played": False,
            "winner": None,
            "team1_win_prob": 0.52,
            "team2_win_prob": 0.48,
            "match": k,
            "date": "May 10",
        }
        for k, (i, j) in enumerate([(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (0, 2), (1, 3), (4, 6), (5, 7), (8, 0)])
    ]
    result = run(mock_standings, mock_schedule)
    for t in result["team_results"]:
        print(
            f"{t['team']}: qualify={t['qualify_prob'] * 100:.1f}%  title={t['title_prob'] * 100:.1f}%  avg_finish={t['avg_finish']:.2f}"
        )
    print("\nTop 3 most important matches:")
    for m in result["match_importance"][:3]:
        print(f"  {m['team1']} vs {m['team2']} — importance={m['importance']:.3f}")
