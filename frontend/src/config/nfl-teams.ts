// frontend/src/config/nfl-teams.ts

export interface TeamIdentity {
  colors: {
    primary: string;
    secondary: string;
  };
  name: string;
}

export const NFL_TEAMS: Record<string, TeamIdentity> = {
  ARI: { name: "Cardinals", colors: { primary: "#97233F", secondary: "#000000" } },
  ATL: { name: "Falcons", colors: { primary: "#A71930", secondary: "#000000" } },
  BAL: { name: "Ravens", colors: { primary: "#241773", secondary: "#000000" } },
  BUF: { name: "Bills", colors: { primary: "#00338D", secondary: "#C60C30" } },
  CAR: { name: "Panthers", colors: { primary: "#0085CA", secondary: "#101820" } },
  CHI: { name: "Bears", colors: { primary: "#0B162A", secondary: "#C83803" } },
  CIN: { name: "Bengals", colors: { primary: "#FB4F14", secondary: "#000000" } },
  CLE: { name: "Browns", colors: { primary: "#311D00", secondary: "#FF3C00" } },
  DAL: { name: "Cowboys", colors: { primary: "#003594", secondary: "#041E42" } },
  DEN: { name: "Broncos", colors: { primary: "#FB4F14", secondary: "#002244" } },
  DET: { name: "Lions", colors: { primary: "#0076B6", secondary: "#B0B7BC" } },
  GB: { name: "Packers", colors: { primary: "#203731", secondary: "#FFB612" } },
  HOU: { name: "Texans", colors: { primary: "#03202F", secondary: "#A71930" } },
  IND: { name: "Colts", colors: { primary: "#002C5F", secondary: "#A2AAAD" } },
  JAX: { name: "Jaguars", colors: { primary: "#006778", secondary: "#9F792C" } },
  KC: { name: "Chiefs", colors: { primary: "#E31837", secondary: "#FFB81C" } },
  LV: { name: "Raiders", colors: { primary: "#000000", secondary: "#A5ACAF" } },
  LAC: { name: "Chargers", colors: { primary: "#0080C6", secondary: "#FFC20E" } },
  LAR: { name: "Rams", colors: { primary: "#003594", secondary: "#FFA300" } },
  MIA: { name: "Dolphins", colors: { primary: "#008E97", secondary: "#FC4C02" } },
  MIN: { name: "Vikings", colors: { primary: "#4F2683", secondary: "#FFC62F" } },
  NE: { name: "Patriots", colors: { primary: "#002244", secondary: "#C60C30" } },
  NO: { name: "Saints", colors: { primary: "#D3BC8D", secondary: "#101820" } },
  NYG: { name: "Giants", colors: { primary: "#002244", secondary: "#a71930" } },
  NYJ: { name: "Jets", colors: { primary: "#125740", secondary: "#000000" } },
  PHI: { name: "Eagles", colors: { primary: "#004C54", secondary: "#A5ACAF" } },
  PIT: { name: "Steelers", colors: { primary: "#FFB612", secondary: "#101820" } },
  SEA: { name: "Seahawks", colors: { primary: "#002244", secondary: "#69BE28" } },
  SF: { name: "49ers", colors: { primary: "#AA0000", secondary: "#B3995D" } },
  TB: { name: "Buccaneers", colors: { primary: "#D50A0A", secondary: "#FF7900" } },
  TEN: { name: "Titans", colors: { primary: "#0C2340", secondary: "#4B92DB" } },
  WAS: { name: "Commanders", colors: { primary: "#5A1414", secondary: "#FFB612" } },
};

export const getTeamColors = (teamAbbr: string | null | undefined) => {
  if (!teamAbbr || !NFL_TEAMS[teamAbbr]) {
    // Default fallback (Generic NFL Blue/Grey)
    return { primary: "#0F172A", secondary: "#64748B" };
  }
  return NFL_TEAMS[teamAbbr].colors;
};


