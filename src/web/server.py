from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from src.web import queries
from src.web import queries_supabase
from src.database.supabase_client import SupabaseClient, SupabaseConfig, SupabaseError
from src.utils.env import load_env


load_env()


INDEX_HTML = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NFL DB Viewer</title>
    <style>
      :root {
        --bg: #0b1220;
        --panel: rgba(255,255,255,0.06);
        --panel2: rgba(255,255,255,0.08);
        --border: rgba(255,255,255,0.10);
        --text: rgba(255,255,255,0.92);
        --muted: rgba(255,255,255,0.62);
        --accent: #7c5cff;
        --good: #33d69f;
        --warn: #ffcc66;
      }
      html, body { height: 100%; }
      body {
        margin: 0;
        font-family: ui-sans-serif, -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
        background: radial-gradient(1200px 500px at 30% 0%, rgba(124,92,255,0.25), transparent 60%),
                    radial-gradient(900px 400px at 80% 10%, rgba(51,214,159,0.18), transparent 55%),
                    var(--bg);
        color: var(--text);
      }
      .wrap { max-width: 1120px; margin: 0 auto; padding: 28px 18px 44px; }
      .topbar { display:flex; align-items:flex-start; justify-content:space-between; gap: 12px; }
      h2 { margin: 0 0 6px; font-size: 26px; letter-spacing: -0.02em; }
      h3 { margin: 22px 0 10px; font-size: 16px; color: var(--muted); font-weight: 650; letter-spacing: 0.02em; text-transform: uppercase; }
      .muted { color: var(--muted); }
      .err { color: #ff6b6b; font-weight: 650; }
      .btn {
        appearance:none; border: 1px solid var(--border); background: rgba(255,255,255,0.06);
        color: var(--text); border-radius: 10px; padding: 10px 12px; cursor: pointer;
      }
      .btn:hover { background: rgba(255,255,255,0.10); }
      .cards { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
      @media (max-width: 1100px) { .cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
      @media (max-width: 700px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      .card {
        border: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
        border-radius: 14px;
        padding: 12px 12px 10px;
        min-height: 76px;
      }
      .label { font-size: 12px; color: var(--muted); }
      .value { font-size: 22px; font-weight: 800; margin-top: 6px; letter-spacing: -0.02em; }
      .sub { margin-top: 6px; font-size: 12px; color: var(--muted); }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
      @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
      .panel {
        border: 1px solid var(--border);
        background: var(--panel);
        border-radius: 14px;
        padding: 12px;
        overflow: hidden;
      }
      .pill { display:inline-flex; align-items:center; gap: 8px; font-size: 12px; color: var(--muted); }
      .dot { width: 8px; height: 8px; border-radius: 999px; background: var(--good); }
      .dot.warn { background: var(--warn); }
      code { background: rgba(255,255,255,0.09); padding: 2px 6px; border-radius: 8px; border: 1px solid var(--border); }
      table { border-collapse: collapse; width: 100%; margin-top: 10px; }
      th, td { border-bottom: 1px solid rgba(255,255,255,0.10); padding: 8px 8px; text-align: left; font-size: 13px; }
      th { color: rgba(255,255,255,0.75); font-weight: 650; }
      .empty { padding: 10px 0; color: var(--muted); }
      .bar { height: 10px; border-radius: 999px; background: rgba(255,255,255,0.10); overflow: hidden; }
      .bar > div { height: 100%; background: linear-gradient(90deg, var(--accent), rgba(124,92,255,0.55)); }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="topbar">
        <div>
          <h2>NFL Analytics DB Viewer</h2>
          <div class="muted">Live read-only view of what’s currently in <code>data/nfl_data.db</code>.</div>
          <div id="error" class="err"></div>
        </div>
        <button class="btn" onclick="location.reload()">Refresh</button>
      </div>

      <div class="cards" id="summary"></div>

      <div class="panel" style="margin-top:14px">
        <div class="pill"><span class="dot"></span>Filters</div>
        <div class="row" style="margin-top:10px; gap:10px; align-items:center">
          <label class="muted">Season&nbsp;
            <select id="seasonSel" class="btn" style="padding:8px 10px"></select>
          </label>
          <label class="muted">Week&nbsp;
            <select id="weekSel" class="btn" style="padding:8px 10px"></select>
          </label>
          <label class="muted">Team&nbsp;
            <select id="teamSel" class="btn" style="padding:8px 10px"></select>
          </label>
          <span class="muted">Tip: click a team or player to drill in.</span>
        </div>
      </div>

      <h3>Leaderboards (works without PFR)</h3>
      <div class="grid">
        <div class="panel">
          <div class="pill"><span class="dot"></span>Top targets (game-level)</div>
          <table id="targets"></table>
        </div>
        <div class="panel">
          <div class="pill"><span class="dot"></span>Top rushing (game-level)</div>
          <table id="epa"></table>
        </div>
        <div class="panel">
          <div class="pill"><span class="dot"></span>Receiving leaders (season)</div>
          <table id="aypt"></table>
        </div>
        <div class="panel">
          <div class="pill"><span class="dot"></span>Rushing leaders (season)</div>
          <table id="tshare"></table>
        </div>
      </div>

      <h3>Routes/YPRR status (requires PFR routes)</h3>
      <div class="panel">
        <div class="pill"><span class="dot warn"></span>YPRR depends on routes; routes come from PFR scraping.</div>
        <div class="muted" style="margin-top:8px">
          PFR live scraping is blocked here (HTTP 403), so expect YPRR to be empty until routes are ingested.
        </div>
        <div style="margin-top:10px" class="bar"><div id="routesbar" style="width:0%"></div></div>
        <div id="routesnote" class="sub"></div>
      </div>

      <h3>Notes</h3>
      <div class="panel">
        <div class="muted">DB path: <code id="dbpath"></code></div>
        <div class="muted" style="margin-top:8px">Tip: open API JSON directly at <code>/api/summary</code>.</div>
      </div>
    </div>

    <script>
      async function getJSON(path) {
        const res = await fetch(path);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return await res.json();
      }
      function card(title, value) {
        return `<div class="card"><div class="label">${title}</div><div class="value">${value}</div></div>`;
      }
      function renderTable(el, rows, cols) {
        if (!rows || rows.length === 0) {
          el.innerHTML = "<tr><td class='empty'>No rows yet</td></tr>";
          return;
        }
        function cell(col, row) {
          const v = (row[col] ?? "").toString();
          if (col === "player_id" && v) {
            return `<a href="/player/${encodeURIComponent(v)}" style="color: var(--text); text-decoration: none; border-bottom: 1px solid rgba(255,255,255,0.25)">${v}</a>`;
          }
          return v;
        }
        el.innerHTML = "<thead><tr>" + cols.map(c => `<th>${c}</th>`).join("") + "</tr></thead>"
          + "<tbody>" + rows.map(r => "<tr>" + cols.map(c => `<td>${cell(c, r)}</td>`).join("") + "</tr>").join("") + "</tbody>";
      }
      (async () => {
        try {
          const opts = await getJSON("/api/options");
          const qp = new URLSearchParams(location.search);
          const state = {
            season: qp.get("season") || (opts.seasons?.[0] ?? ""),
            week: qp.get("week") || "",
            team: qp.get("team") || "",
            tab: qp.get("tab") || "receiving_game"
          };

          function setQP() {
            const p = new URLSearchParams();
            if (state.season) p.set("season", state.season);
            if (state.week) p.set("week", state.week);
            if (state.team) p.set("team", state.team);
            if (state.tab) p.set("tab", state.tab);
            history.replaceState(null, "", "?" + p.toString());
          }

          // Render filters
          function opt(label, value, selected) {
            return `<option value="${value}" ${selected ? "selected":""}>${label}</option>`;
          }
          const seasonSel = document.getElementById("seasonSel");
          seasonSel.innerHTML = opts.seasons.map(s => opt(s, s, String(s) === String(state.season))).join("");
          const weekSel = document.getElementById("weekSel");
          weekSel.innerHTML = opt("All Weeks", "", state.week==="") + opts.weeks.map(w => opt("Week " + w, w, String(w) === String(state.week))).join("");
          const teamSel = document.getElementById("teamSel");
          teamSel.innerHTML = opt("All Teams", "", state.team==="") + opts.teams.map(t => opt(t, t, String(t) === String(state.team))).join("");

          function onChange() {
            state.season = seasonSel.value;
            state.week = weekSel.value;
            state.team = teamSel.value;
            setQP();
            refreshTables();
          }
          seasonSel.onchange = onChange;
          weekSel.onchange = onChange;
          teamSel.onchange = onChange;

          const s = await getJSON("/api/summary");
          document.getElementById("dbpath").textContent = s.db_path;
          document.getElementById("summary").innerHTML =
            card("Seasons", s.seasons.join(", ")) +
            card("Games", s.games) +
            card("Plays", s.plays) +
            card("Players", s.players) +
            card("Usage rows", s.player_usage_metrics) +
            card("Season aggregates", s.season_aggregates);

          const routesPct = s.routes_coverage_pct ?? 0;
          document.getElementById("routesbar").style.width = `${routesPct}%`;
          document.getElementById("routesnote").textContent = `Routes coverage: ${routesPct.toFixed(1)}% of player-game rows have routes.`;

          function num(x) { return (x === null || x === undefined || x === "") ? null : Number(x); }

          function renderWithSort(el, rows, columns, defaultKey) {
            let sortKey = defaultKey;
            let asc = false;

            function th(col) {
              const arrow = (sortKey === col.key) ? (asc ? " ▲" : " ▼") : "";
              return `<th data-k="${col.key}" style="cursor:pointer">${col.label}${arrow}</th>`;
            }
            function fmt(col, v) {
              if (v === null || v === undefined || v === "") return "";
              if (col.fmt === "pct") {
                const n = Number(v);
                if (!Number.isFinite(n)) return v.toString();
                return (n * 100).toFixed(1) + "%";
              }
              if (col.type === "number") {
                const n = Number(v);
                if (!Number.isFinite(n)) return v.toString();
                // integers as-is; otherwise show up to 3 decimals.
                if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
                return n.toFixed(3);
              }
              return v.toString();
            }
            function td(col, row) {
              if (col.key === "player_name") {
                const pid = row["player_id"];
                const name = (row["player_name"] ?? "").toString() || pid;
                return `<td><a href="/player/${encodeURIComponent(pid)}" style="color: var(--text); text-decoration: none; border-bottom: 1px solid rgba(255,255,255,0.25)">${name}</a></td>`;
              }
              if (col.key === "team") {
                const t = (row["team"] ?? "").toString();
                return `<td><a href="/team/${encodeURIComponent(t)}?season=${encodeURIComponent(state.season)}" style="color: var(--text); text-decoration:none; border-bottom:1px solid rgba(255,255,255,0.20)">${t}</a></td>`;
              }
              const v = row[col.key];
              return `<td>${fmt(col, v)}</td>`;
            }
            function sortRows() {
              const col = columns.find(c => c.key === sortKey) || columns[0];
              const copy = rows.slice();
              copy.sort((a,b) => {
                const av = a[sortKey], bv = b[sortKey];
                if (col.type === "number") {
                  const an = num(av) ?? -Infinity;
                  const bn = num(bv) ?? -Infinity;
                  return asc ? (an - bn) : (bn - an);
                }
                const as = (av ?? "").toString();
                const bs = (bv ?? "").toString();
                return asc ? as.localeCompare(bs) : bs.localeCompare(as);
              });
              return copy;
            }
            function draw() {
              if (!rows || rows.length === 0) {
                el.innerHTML = "<tr><td class='empty'>No rows yet</td></tr>";
                return;
              }
              const sorted = sortRows();
              el.innerHTML =
                "<thead><tr>" + columns.map(th).join("") + "</tr></thead>" +
                "<tbody>" + sorted.map(r => "<tr>" + columns.map(c => td(c,r)).join("") + "</tr>").join("") + "</tbody>";
              el.querySelectorAll("th[data-k]").forEach(h => {
                h.onclick = () => {
                  const k = h.getAttribute("data-k");
                  if (!k) return;
                  if (sortKey === k) asc = !asc;
                  else { sortKey = k; asc = false; }
                  draw();
                };
              });
            }
            draw();
          }

          async function refreshTables() {
            const base = new URLSearchParams();
            if (state.season) base.set("season", state.season);
            if (state.week) base.set("week", state.week);
            if (state.team) base.set("team", state.team);
            base.set("limit", "25");

            const recvGame = await getJSON("/api/receiving_dashboard?" + base.toString());
            renderWithSort(
              document.getElementById("targets"),
              recvGame.rows,
              [
                {key:"season", label:"Season", type:"number"},
                {key:"week", label:"Week", type:"number"},
                {key:"team", label:"Team", type:"string"},
                {key:"player_name", label:"Player", type:"string"},
                {key:"position", label:"Pos", type:"string"},
                {key:"targets", label:"Targets", type:"number"},
                {key:"receptions", label:"Receptions", type:"number"},
                {key:"rec_yards", label:"Rec Yds", type:"number"},
                {key:"air_yards", label:"Air Yds", type:"number"},
                {key:"epa_per_target", label:"EPA/Tgt", type:"number"},
              ],
              "targets"
            );

            const rushGame = await getJSON("/api/rushing_dashboard?" + base.toString());
            renderWithSort(
              document.getElementById("epa"),
              rushGame.rows,
              [
                {key:"season", label:"Season", type:"number"},
                {key:"week", label:"Week", type:"number"},
                {key:"team", label:"Team", type:"string"},
                {key:"player_name", label:"Player", type:"string"},
                {key:"position", label:"Pos", type:"string"},
                {key:"rush_attempts", label:"Rush Att", type:"number"},
                {key:"rush_yards", label:"Rush Yds", type:"number"},
                {key:"epa_per_rush", label:"EPA/Rush", type:"number"},
              ],
              "rush_yards"
            );

            const recvSeason = await getJSON("/api/receiving_season?" + base.toString());
            renderWithSort(
              document.getElementById("aypt"),
              recvSeason.rows,
              [
                {key:"season", label:"Season", type:"number"},
                {key:"team", label:"Team", type:"string"},
                {key:"player_name", label:"Player", type:"string"},
                {key:"position", label:"Pos", type:"string"},
                {key:"targets", label:"Targets", type:"number"},
                {key:"receptions", label:"Receptions", type:"number"},
                {key:"rec_yards", label:"Rec Yds", type:"number"},
                {key:"air_yards", label:"Air Yds", type:"number"},
                {key:"team_target_share", label:"Team Target %", type:"number", fmt:"pct"},
              ],
              "targets"
            );

            const rushSeason = await getJSON("/api/rushing_season?" + base.toString());
            renderWithSort(
              document.getElementById("tshare"),
              rushSeason.rows,
              [
                {key:"season", label:"Season", type:"number"},
                {key:"team", label:"Team", type:"string"},
                {key:"player_name", label:"Player", type:"string"},
                {key:"position", label:"Pos", type:"string"},
                {key:"rush_attempts", label:"Rush Att", type:"number"},
                {key:"rush_yards", label:"Rush Yds", type:"number"},
                {key:"team_rush_share", label:"Team Rush %", type:"number", fmt:"pct"},
              ],
              "rush_yards"
            );
          }

          await refreshTables();
        } catch (e) {
          document.getElementById("error").textContent = "Error: " + e.message;
        }
      })();
    </script>
  </body>
</html>
"""


def _dict_rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


class Handler(BaseHTTPRequestHandler):
    db_path: Path
    dist_path: Path
    _supabase: Optional[SupabaseClient] = None

    def _supabase_client(self) -> Optional[SupabaseClient]:
        # Enabled if the required env vars are set.
        if Handler._supabase is not None:
            return Handler._supabase
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            return None
        try:
            Handler._supabase = SupabaseClient(SupabaseConfig(url=url, service_role_key=key))
        except SupabaseError:
            return None
        return Handler._supabase

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c
    
    def _serve_static_file(self, file_path: Path) -> None:
        """Serve a static file from the dist directory."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type is None:
                content_type = 'application/octet-stream'
            
            self._send(200, content, content_type)
        except FileNotFoundError:
            self._json({"error": "File not found"}, code=404)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        sb = self._supabase_client()

        def q_int(name: str) -> Optional[int]:
            raw = qs.get(name, [None])[0]
            if raw in (None, "", "null"):
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        def q_str(name: str) -> Optional[str]:
            raw = qs.get(name, [None])[0]
            if raw in (None, "", "null"):
                return None
            return str(raw)

        # API endpoints
        if path == "/api/summary":
            if sb is not None:
                s = queries_supabase.summary(sb)
                s["db_path"] = "supabase"
                self._json(s)
            else:
                with self._conn() as conn:
                    s = queries.summary(conn)
                s["db_path"] = str(self.db_path)
                self._json(s)
            return

        if path == "/api/options":
            if sb is not None:
                self._json(queries_supabase.options(sb))
            else:
                with self._conn() as conn:
                    self._json(queries.options(conn))
            return

        if path == "/api/players":
            # Default high to avoid hiding valid players when the UI requests "all skill players with stats".
            limit = int(qs.get("limit", ["12000"])[0])
            if sb is not None:
                players = queries_supabase.get_players_list(
                    sb,
                    season=q_int("season"),
                    position=q_str("position"),
                    team=q_str("team"),
                    limit=limit,
                )
                self._json({"players": players})
            else:
                with self._conn() as conn:
                    players = queries.get_players_list(
                        conn,
                        season=q_int("season"),
                        position=q_str("position"),
                        team=q_str("team"),
                        limit=limit,
                    )
                # Attach photoUrl (GSIS -> ESPN/Sleeper) for the UI
                for p in players:
                    p["photoUrl"] = queries.player_photo_url(p.get("player_id", ""))  # type: ignore[arg-type]
                    # Normalize naming to what the frontend expects
                    if "player_position" in p and "position" not in p:
                        p["position"] = p.get("player_position")
                self._json({"players": players})
            return

        if path.startswith("/api/player/"):
            player_id = path.split("/api/player/", 1)[1].strip()
            season = q_int("season")
            include_postseason = (qs.get("include_postseason", ["0"])[0] or "0").strip() in {"1", "true", "TRUE", "yes", "YES"}
            if not player_id or not season:
                self._json({"error": "missing player_id or season"}, code=400)
                return
            if sb is not None:
                # Minimal core response: find player in Supabase and return empty gameLogs for now.
                try:
                    pid_int = int(player_id)
                except Exception:
                    self._json({"error": "invalid player_id"}, code=400)
                    return

                rows = sb.select(
                    "nfl_players",
                    select="id,first_name,last_name,position_abbreviation,team_id",
                    filters={"id": f"eq.{pid_int}"},
                    limit=1,
                )
                if not rows:
                    self._json({"error": "player not found"}, code=404)
                    return
                r = rows[0]
                team_abbr = None
                tid = r.get("team_id")
                if tid not in (None, ""):
                    teams = sb.select("nfl_teams", select="abbreviation", filters={"id": f"eq.{int(tid)}"}, limit=1)
                    if teams:
                        team_abbr = teams[0].get("abbreviation")
                name = (str(r.get("first_name") or "").strip() + " " + str(r.get("last_name") or "").strip()).strip() or str(pid_int)
                player = {
                    "player_id": str(pid_int),
                    "player_name": name,
                    "team": team_abbr,
                    "position": r.get("position_abbreviation"),
                    "season": season,
                }
                player["photoUrl"] = queries_supabase.player_photo_url_from_name_team(name=name, team=team_abbr)
                # Season totals from nfl_player_season_stats (if present)
                st = sb.select(
                    "nfl_player_season_stats",
                    select=(
                        "games_played,receiving_targets,receptions,receiving_yards,receiving_touchdowns,"
                        "rushing_attempts,rushing_yards,rushing_touchdowns,"
                        "passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,qbr,qb_rating"
                    ),
                    filters={"player_id": f"eq.{pid_int}", "season": f"eq.{int(season)}", "postseason": "eq.false"},
                    limit=1,
                )
                stats = st[0] if st else {}
                games = int(stats.get("games_played") or 0)
                targets = int(stats.get("receiving_targets") or 0)
                rec = int(stats.get("receptions") or 0)
                rec_yards = int(stats.get("receiving_yards") or 0)
                rec_tds = int(stats.get("receiving_touchdowns") or 0)
                rush_att = int(stats.get("rushing_attempts") or 0)
                rush_yards = int(stats.get("rushing_yards") or 0)
                rush_tds = int(stats.get("rushing_touchdowns") or 0)
                pass_att = int(stats.get("passing_attempts") or 0)
                pass_cmp = int(stats.get("passing_completions") or 0)
                pass_yds = int(stats.get("passing_yards") or 0)
                pass_tds = int(stats.get("passing_touchdowns") or 0)
                pass_int = int(stats.get("passing_interceptions") or 0)
                qb_rating = stats.get("qb_rating")
                qbr = stats.get("qbr")
                player["seasonTotals"] = {
                    "season": season,
                    "games": games,
                    "targets": targets,
                    "receptions": rec,
                    "receivingYards": rec_yards,
                    "receivingTouchdowns": rec_tds,
                    "avgYardsPerCatch": (rec_yards / rec) if rec else 0,
                    "rushAttempts": rush_att,
                    "rushingYards": rush_yards,
                    "rushingTouchdowns": rush_tds,
                    "avgYardsPerRush": (rush_yards / rush_att) if rush_att else 0,
                    "passingAttempts": pass_att,
                    "passingCompletions": pass_cmp,
                    "passingYards": pass_yds,
                    "passingTouchdowns": pass_tds,
                    "passingInterceptions": pass_int,
                    "qbRating": qb_rating,
                    "qbr": qbr,
                }
                game_logs = queries_supabase.get_player_game_logs(sb, player_id=str(pid_int), season=season, include_postseason=include_postseason)
                self._json({"player": player, "gameLogs": game_logs})
            else:
                with self._conn() as conn:
                    # Get player info
                    cur = conn.cursor()
                    player_row = cur.execute(
                        """SELECT player_id, player_name, position, team_abbr as team 
                           FROM players WHERE player_id = ?""",
                        (player_id,),
                    ).fetchone()
                    
                    if not player_row:
                        self._json({"error": "player not found"}, code=404)
                        return
                    
                    player = dict(player_row)
                    
                    # Get season totals
                    season_stats = queries.get_players_list(
                        conn, season=season, position=None, team=None, limit=1000
                    )
                    player_season = next((p for p in season_stats if p['player_id'] == player_id), None)
                    
                    if player_season:
                        # Prefer derived team/position from season aggregates (players table may be sparse)
                        player["team"] = player_season.get("team")
                        player["position"] = player_season.get("player_position") or player.get("position")
                        player.update({
                            'seasonTotals': {
                                'season': season,
                                'games': player_season.get('games', 0),
                                'targets': player_season.get('targets', 0),
                                'receptions': player_season.get('receptions', 0),
                                'receivingYards': player_season.get('receivingYards', 0),
                                'receivingTouchdowns': player_season.get('receivingTouchdowns', 0),
                                'avgYardsPerCatch': player_season.get('avgYardsPerCatch', 0),
                                'rushAttempts': player_season.get('rushAttempts', 0),
                                'rushingYards': player_season.get('rushingYards', 0),
                                'rushingTouchdowns': player_season.get('rushingTouchdowns', 0),
                                'avgYardsPerRush': player_season.get('avgYardsPerRush', 0),
                            }
                        })
                    # Photo URL for the hero + card
                    player["photoUrl"] = queries.player_photo_url(player_id)
                    
                    # Get game logs
                    game_logs = queries.get_player_game_logs(conn, player_id, season, include_postseason=include_postseason)
                    
                self._json({"player": player, "gameLogs": game_logs})
            return

        if path == "/api/receiving_dashboard":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                week = q_int("week")
                if season is None or week is None:
                    self._json({"error": "missing season or week"}, code=400)
                    return
                rows = queries_supabase.receiving_dashboard(
                    sb,
                    season=season,
                    week=week,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                with self._conn() as conn:
                    rows = queries.player_game_receiving(
                        conn,
                        season=q_int("season"),
                        week=q_int("week"),
                        team=q_str("team"),
                        limit=limit,
                    )
                for r in rows:
                    r["photoUrl"] = queries.player_photo_url(r.get("player_id", ""))  # type: ignore[arg-type]
                    # players table can be sparse; receiving leaderboards are overwhelmingly WR/TE/RB
                    r["position"] = r.get("position") if r.get("position") not in (None, "", "UNK") else "WR"
                self._json({"rows": rows})
            return

        if path == "/api/rushing_dashboard":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                week = q_int("week")
                if season is None or week is None:
                    self._json({"error": "missing season or week"}, code=400)
                    return
                rows = queries_supabase.rushing_dashboard(
                    sb,
                    season=season,
                    week=week,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                with self._conn() as conn:
                    rows = queries.player_game_rushing(
                        conn,
                        season=q_int("season"),
                        week=q_int("week"),
                        team=q_str("team"),
                        limit=limit,
                    )
                for r in rows:
                    r["photoUrl"] = queries.player_photo_url(r.get("player_id", ""))  # type: ignore[arg-type]
                    r["position"] = r.get("position") if r.get("position") not in (None, "", "UNK") else "RB"
                self._json({"rows": rows})
            return

        if path == "/api/passing_dashboard":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                week = q_int("week")
                if season is None or week is None:
                    self._json({"error": "missing season or week"}, code=400)
                    return
                rows = queries_supabase.passing_dashboard(
                    sb,
                    season=season,
                    week=week,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                self._json({"error": "passing_dashboard not supported without Supabase"}, code=501)
            return

        if path == "/api/receiving_season":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                if season is None:
                    self._json({"error": "missing season"}, code=400)
                    return
                rows = queries_supabase.receiving_season(sb, season=season, team=q_str("team"), limit=limit)
                self._json({"rows": rows})
            else:
                with self._conn() as conn:
                    rows = queries.season_receiving(
                        conn,
                        season=q_int("season"),
                        team=q_str("team"),
                        limit=limit,
                    )
                for r in rows:
                    r["photoUrl"] = queries.player_photo_url(r.get("player_id", ""))  # type: ignore[arg-type]
                    r["position"] = r.get("position") if r.get("position") not in (None, "", "UNK") else "WR"
                self._json({"rows": rows})
            return

        if path == "/api/rushing_season":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                if season is None:
                    self._json({"error": "missing season"}, code=400)
                    return
                rows = queries_supabase.rushing_season(
                    sb,
                    season=season,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                with self._conn() as conn:
                    rows = queries.season_rushing(
                        conn,
                        season=q_int("season"),
                        team=q_str("team"),
                        limit=limit,
                    )
                for r in rows:
                    r["photoUrl"] = queries.player_photo_url(r.get("player_id", ""))  # type: ignore[arg-type]
                    r["position"] = r.get("position") if r.get("position") not in (None, "", "UNK") else "RB"
                self._json({"rows": rows})
            return

        if path == "/api/passing_season":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                if season is None:
                    self._json({"error": "missing season"}, code=400)
                    return
                rows = queries_supabase.passing_season(
                    sb,
                    season=season,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                self._json({"error": "passing_season not supported without Supabase"}, code=501)
            return

        if path == "/api/total_yards_dashboard":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                week = q_int("week")
                if season is None or week is None:
                    self._json({"error": "missing season or week"}, code=400)
                    return
                rows = queries_supabase.total_yards_dashboard(
                    sb,
                    season=season,
                    week=week,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                self._json({"error": "total_yards_dashboard not supported without Supabase"}, code=501)
            return

        if path == "/api/total_yards_season":
            limit = int(qs.get("limit", ["25"])[0])
            if sb is not None:
                season = q_int("season")
                if season is None:
                    self._json({"error": "missing season"}, code=400)
                    return
                rows = queries_supabase.total_yards_season(
                    sb,
                    season=season,
                    team=q_str("team"),
                    position=q_str("position"),
                    limit=limit,
                )
                self._json({"rows": rows})
            else:
                self._json({"error": "total_yards_season not supported without Supabase"}, code=501)
            return

        # Legacy endpoints for old UI
        if path.startswith("/player/"):
            player_id = path.split("/player/", 1)[1].strip()
            if not player_id:
                self._json({"error": "missing player_id"}, code=400)
                return
            self._send(200, self._render_player_page(player_id).encode("utf-8"), "text/html; charset=utf-8")
            return

        if path.startswith("/team/"):
            team_abbr = path.split("/team/", 1)[1].strip().upper()
            if not team_abbr:
                self._json({"error": "missing team"}, code=400)
                return
            season = qs.get("season", [None])[0]
            week = qs.get("week", [None])[0]
            self._send(
                200,
                self._render_team_page(team_abbr, season=season, week=week).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        # Serve React app
        if self.dist_path.exists():
            # Serve index.html for root or any non-asset path (SPA routing)
            if path == "/" or path == "/index.html":
                index_file = self.dist_path / "index.html"
                if index_file.exists():
                    self._serve_static_file(index_file)
                    return
            
            # Serve static assets
            requested_file = self.dist_path / path.lstrip('/')
            if requested_file.exists() and requested_file.is_file():
                self._serve_static_file(requested_file)
                return
            
            # Fallback to index.html for SPA routing
            index_file = self.dist_path / "index.html"
            if index_file.exists():
                self._serve_static_file(index_file)
                return

        # Fallback to old UI if dist doesn't exist
        if path == "/" or path == "/index.html":
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        self._json({"error": "not found", "path": path}, code=404)

    def _render_player_page(self, player_id: str) -> str:
        with self._conn() as conn:
            cur = conn.cursor()
            p = cur.execute(
                "SELECT player_id, COALESCE(player_name,'') AS player_name, COALESCE(position,'') AS position, COALESCE(team_abbr,'') AS team_abbr FROM players WHERE player_id = ?",
                (player_id,),
            ).fetchone()
            if not p:
                return f"<h2>Player not found</h2><div class='muted'>player_id={player_id}</div><a href='/'>Back</a>"

            season = cur.execute(
                """
                SELECT season, team_abbr, targets, total_routes, ROUND(target_share, 4) AS target_share, ROUND(air_yards_share,4) AS air_yards_share
                FROM season_aggregates
                WHERE player_id = ?
                ORDER BY season DESC
                LIMIT 4
                """,
                (player_id,),
            ).fetchall()

            games = cur.execute(
                """
                SELECT
                    u.season, u.week, u.game_id, u.team_abbr,
                    g.home_team, g.away_team,
                    u.targets,
                    ROUND(e.epa_per_target,4) AS epa_per_target,
                    ROUND(e.air_yards_per_target,3) AS air_yards_per_target
                FROM player_usage_metrics u
                LEFT JOIN player_efficiency_metrics e
                  ON e.player_id = u.player_id AND e.game_id = u.game_id
                LEFT JOIN games g ON g.game_id = u.game_id
                WHERE u.player_id = ?
                ORDER BY u.season DESC, u.week DESC, u.targets DESC
                LIMIT 25
                """,
                (player_id,),
            ).fetchall()

        def tr(cells: list[str]) -> str:
            return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

        season_rows = ""
        for r in season:
            season_rows += tr(
                [
                    str(r["season"]),
                    str(r["team_abbr"] or ""),
                    str(r["targets"] or 0),
                    str(r["total_routes"] or ""),
                    str(r["target_share"] or ""),
                    str(r["air_yards_share"] or ""),
                ]
            )

        game_rows = ""
        for r in games:
            ht = (r["home_team"] or "").strip()
            at = (r["away_team"] or "").strip()
            team = (r["team_abbr"] or "").strip()
            opp = ""
            if team and ht and at:
                opp = f"@ {at}" if team == ht else f"vs {ht}"
            game_rows += tr(
                [
                    str(r["season"]),
                    str(r["week"]),
                    str(r["team_abbr"] or ""),
                    (opp or f"<code>{r['game_id']}</code>"),
                    str(r["targets"] or 0),
                    str(r["epa_per_target"] or ""),
                    str(r["air_yards_per_target"] or ""),
                ]
            )

        return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{p['player_name'] or p['player_id']}</title>
    <style>{INDEX_HTML.split('<style>')[1].split('</style>')[0]}</style>
  </head>
  <body>
    <div class="wrap">
      <div class="topbar">
        <div>
          <h2>{p['player_name'] or p['player_id']}</h2>
          <div class="muted"><code>{p['player_id']}</code> · {p['position'] or 'UNK'} · {p['team_abbr'] or ''}</div>
        </div>
        <a class="btn" href="/">Back</a>
      </div>

      <h3>Season summary</h3>
      <div class="panel">
        <table>
          <thead><tr><th>season</th><th>team</th><th>targets</th><th>routes</th><th>target_share</th><th>air_yards_share</th></tr></thead>
          <tbody>{season_rows or "<tr><td class='empty' colspan='6'>No season aggregates yet</td></tr>"}</tbody>
        </table>
      </div>

      <h3>Recent games</h3>
      <div class="panel">
        <table>
          <thead><tr><th>Season</th><th>Week</th><th>Team</th><th>Game</th><th>Targets</th><th>EPA/Target</th><th>Air/Target</th></tr></thead>
          <tbody>{game_rows or "<tr><td class='empty' colspan='7'>No games yet</td></tr>"}</tbody>
        </table>
      </div>
    </div>
  </body>
</html>"""

    def _render_team_page(self, team_abbr: str, *, season: Optional[str], week: Optional[str]) -> str:
        season_i = int(season) if season and season.isdigit() else None
        week_i = int(week) if week and week.isdigit() else None
        with self._conn() as conn:
            recv = queries.player_game_receiving(conn, season=season_i, week=week_i, team=team_abbr, limit=25)
            rush = queries.player_game_rushing(conn, season=season_i, week=week_i, team=team_abbr, limit=25)
            seas_recv = queries.season_receiving(conn, season=season_i, team=team_abbr, limit=25)
            seas_rush = queries.season_rushing(conn, season=season_i, team=team_abbr, limit=25)

        def rows_to_tr(rows: list[dict[str, Any]], cols: list[str]) -> str:
            out = ""
            for r in rows:
                tds = []
                for c in cols:
                    if c == "player_name":
                        pid = r.get("player_id", "")
                        name = r.get("player_name", pid) or pid
                        tds.append(f"<a href='/player/{pid}' style='color: var(--text); text-decoration:none; border-bottom:1px solid rgba(255,255,255,0.25)'>{name}</a>")
                    else:
                        v = r.get(c, "")
                        if c in ("team_target_share", "team_rush_share") and v not in ("", None):
                            try:
                                tds.append(f"{float(v)*100:.1f}%")
                            except Exception:
                                tds.append(str(v))
                        else:
                            tds.append(str(v if v is not None else ""))
                out += "<tr>" + "".join(f"<td>{x}</td>" for x in tds) + "</tr>"
            return out

        style = INDEX_HTML.split("<style>")[1].split("</style>")[0]
        tmpl = Template(
            """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>$TEAM Team</title>
    <style>$STYLE</style>
  </head>
  <body>
    <div class="wrap">
      <div class="topbar">
        <div>
          <h2>$TEAM Team Leaders</h2>
          <div class="muted">Filters: season=$SEASON week=$WEEK</div>
        </div>
        <a class="btn" href="/">Back</a>
      </div>

      <div class="panel" style="margin-top:14px">
        <div class="pill"><span class="dot"></span>Team Filters</div>
        <div class="muted" style="margin-top:10px">
          Edit URL params: <code>?season=2024</code> and/or <code>&amp;week=5</code>
        </div>
      </div>

      <h3>Receiving (game-level)</h3>
      <div class="panel">
        <table>
          <thead><tr><th>Season</th><th>Week</th><th>Player</th><th>Pos</th><th>Targets</th><th>Receptions</th><th>Rec Yds</th><th>Air Yds</th><th>EPA/Tgt</th></tr></thead>
          <tbody>$RECV_GAME</tbody>
        </table>
      </div>

      <h3>Rushing (game-level)</h3>
      <div class="panel">
        <table>
          <thead><tr><th>Season</th><th>Week</th><th>Player</th><th>Pos</th><th>Rush Att</th><th>Rush Yds</th><th>EPA/Rush</th></tr></thead>
          <tbody>$RUSH_GAME</tbody>
        </table>
      </div>

      <h3>Receiving (season)</h3>
      <div class="panel">
        <table>
          <thead><tr><th>Season</th><th>Player</th><th>Pos</th><th>Targets</th><th>Receptions</th><th>Rec Yds</th><th>Team Target %</th></tr></thead>
          <tbody>$RECV_SEASON</tbody>
        </table>
      </div>

      <h3>Rushing (season)</h3>
      <div class="panel">
        <table>
          <thead><tr><th>Season</th><th>Player</th><th>Pos</th><th>Rush Att</th><th>Rush Yds</th><th>Team Rush %</th></tr></thead>
          <tbody>$RUSH_SEASON</tbody>
        </table>
      </div>
    </div>
    <script>
      // Make all tables sortable (client-side) by clicking headers.
      document.querySelectorAll("table").forEach(tbl => {
        const ths = tbl.querySelectorAll("thead th");
        const tbody = tbl.querySelector("tbody");
        if (!ths || !tbody) return;
        ths.forEach((th, idx) => {
          th.style.cursor = "pointer";
          th.onclick = () => {
            const rows = Array.from(tbody.querySelectorAll("tr"));
            const asc = th.getAttribute("data-asc") !== "1";
            ths.forEach(h => h.removeAttribute("data-asc"));
            th.setAttribute("data-asc", asc ? "1" : "0");
            rows.sort((a,b) => {
              const av = (a.children[idx]?.textContent || "").trim();
              const bv = (b.children[idx]?.textContent || "").trim();
              const an = Number(av.replace('%',''));
              const bn = Number(bv.replace('%',''));
              const bothNum = Number.isFinite(an) && Number.isFinite(bn);
              if (bothNum) return asc ? (an - bn) : (bn - an);
              return asc ? av.localeCompare(bv) : bv.localeCompare(av);
            });
            rows.forEach(r => tbody.appendChild(r));
          };
        });
      });
    </script>
  </body>
</html>"""
        )

        def or_empty(body: str, cols: int) -> str:
            return body or f"<tr><td class='empty' colspan='{cols}'>No rows</td></tr>"

        return tmpl.safe_substitute(
            TEAM=team_abbr,
            STYLE=style,
            SEASON=(season or "All"),
            WEEK=(week or "All"),
            RECV_GAME=or_empty(
                rows_to_tr(
                    recv,
                    ["season", "week", "player_name", "position", "targets", "receptions", "rec_yards", "air_yards", "epa_per_target"],
                ),
                9,
            ),
            RUSH_GAME=or_empty(
                rows_to_tr(
                    rush,
                    ["season", "week", "player_name", "position", "rush_attempts", "rush_yards", "epa_per_rush"],
                ),
                7,
            ),
            RECV_SEASON=or_empty(
                rows_to_tr(
                    seas_recv,
                    ["season", "player_name", "position", "targets", "receptions", "rec_yards", "team_target_share"],
                ),
                7,
            ),
            RUSH_SEASON=or_empty(
                rows_to_tr(
                    seas_rush,
                    ["season", "player_name", "position", "rush_attempts", "rush_yards", "team_rush_share"],
                ),
                6,
            ),
        )


def run(db_path: str, host: str, port: int) -> None:
    Handler.db_path = Path(db_path).resolve()
    Handler.dist_path = Path(__file__).parent.parent.parent / "dist"
    server = ThreadingHTTPServer((host, port), Handler)
    
    ui_type = "React UI" if Handler.dist_path.exists() else "Legacy UI"
    print(f"Serving {ui_type} at http://{host}:{port}/ (db={Handler.db_path})")
    if Handler.dist_path.exists():
        print(f"Static files from: {Handler.dist_path}")
    
    server.serve_forever()


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Local web viewer for nfl_data.db")
    p.add_argument("--db", default="data/nfl_data.db", help="Path to SQLite DB")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    run(args.db, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


