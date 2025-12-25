import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Player } from "@/types/player";
import { PlayerCard } from "./PlayerCard";

describe("PlayerCard team aura", () => {
  it("renders a gradient aura using the player's team colors", () => {
    const player: Player = {
      player_id: "p1",
      player_name: "Patrick Mahomes",
      team: "KC",
      position: "QB",
    };

    render(<PlayerCard player={player} />);

    const aura = screen.getByTestId("player-team-aura");
    expect(aura).toHaveClass("blur-md");
    expect(aura).toHaveClass("opacity-40");
    expect(aura).toHaveStyle({
      background: "linear-gradient(135deg, #E31837, #FFB81C)",
    });

    const headshot = screen.getByTestId("player-headshot-container");
    expect(headshot).toHaveStyle({ backgroundColor: "#E31837" });
    expect(headshot).toHaveClass("shadow-inner");
  });
});


