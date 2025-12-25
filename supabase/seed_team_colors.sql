-- Seed team colors (NULL-only updates)
--
-- This file is intentionally safe: it ONLY sets colors when they are currently NULL.
-- If you want to change a color later, update the row explicitly.
--
-- Apply after:
--   - supabase/schema_core.sql
--   - supabase/schema_team_colors.sql

begin;

-- Canonical NFL team colors (primary/secondary). Hex values.
-- Source: common team brand palettes (can be edited later).

update public.nfl_teams set primary_color = '#013369' where abbreviation='NFL' and primary_color is null;

-- AFC East
update public.nfl_teams set primary_color = '#00338D', secondary_color = '#C60C30' where abbreviation='BUF' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#008E97', secondary_color = '#FC4C02' where abbreviation='MIA' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#002244', secondary_color = '#C60C30' where abbreviation='NE'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#125740', secondary_color = '#000000' where abbreviation='NYJ' and (primary_color is null or secondary_color is null);

-- AFC North
update public.nfl_teams set primary_color = '#241773', secondary_color = '#000000' where abbreviation='BAL' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#FB4F14', secondary_color = '#000000' where abbreviation='CIN' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#311D00', secondary_color = '#FF3C00' where abbreviation='CLE' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#FFB612', secondary_color = '#101820' where abbreviation='PIT' and (primary_color is null or secondary_color is null);

-- AFC South
update public.nfl_teams set primary_color = '#002C5F', secondary_color = '#A2AAAD' where abbreviation='HOU' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#002C5F', secondary_color = '#A5ACAF' where abbreviation='IND' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#006778', secondary_color = '#9F792C' where abbreviation='JAX' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#4B92DB', secondary_color = '#0C2340' where abbreviation='TEN' and (primary_color is null or secondary_color is null);

-- AFC West
update public.nfl_teams set primary_color = '#FB4F14', secondary_color = '#002244' where abbreviation='DEN' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#E31837', secondary_color = '#FFB81C' where abbreviation='KC'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#000000', secondary_color = '#A5ACAF' where abbreviation='LV'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#0080C6', secondary_color = '#FFC20E' where abbreviation='LAC' and (primary_color is null or secondary_color is null);

-- NFC East
update public.nfl_teams set primary_color = '#002244', secondary_color = '#B0B7BC' where abbreviation='DAL' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#0B2265', secondary_color = '#A71930' where abbreviation='NYG' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#004C54', secondary_color = '#A5ACAF' where abbreviation='PHI' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#5A1414', secondary_color = '#FFB612' where abbreviation='WAS' and (primary_color is null or secondary_color is null);

-- NFC North
update public.nfl_teams set primary_color = '#0B162A', secondary_color = '#C83803' where abbreviation='CHI' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#203731', secondary_color = '#FFB612' where abbreviation='GB'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#0076B6', secondary_color = '#B0B7BC' where abbreviation='DET' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#4F2683', secondary_color = '#FFC62F' where abbreviation='MIN' and (primary_color is null or secondary_color is null);

-- NFC South
update public.nfl_teams set primary_color = '#000000', secondary_color = '#D3BC8D' where abbreviation='NO'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#A71930', secondary_color = '#000000' where abbreviation='TB'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#0085CA', secondary_color = '#101820' where abbreviation='CAR' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#A71930', secondary_color = '#000000' where abbreviation='ATL' and (primary_color is null or secondary_color is null);

-- NFC West
update public.nfl_teams set primary_color = '#97233F', secondary_color = '#000000' where abbreviation='ARI' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#002244', secondary_color = '#69BE28' where abbreviation='SEA' and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#AA0000', secondary_color = '#B3995D' where abbreviation='SF'  and (primary_color is null or secondary_color is null);
update public.nfl_teams set primary_color = '#003594', secondary_color = '#FFA300' where abbreviation='LAR' and (primary_color is null or secondary_color is null);

commit;



