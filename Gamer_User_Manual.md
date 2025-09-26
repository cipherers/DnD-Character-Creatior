# DnD Character Creator – Player Manual

## 1. What This App Does
Create and store D&D characters. The app:
- Lets you (or an admin) add Races, Classes, Weapons, Abilities.
- Rolls ability scores automatically (4d6, drop lowest).
- Applies Race bonuses to final stats.
- Saves characters to your account.

## 2. Basic Flow
1. Register / Log in.
2. (Optional) Add new Race / Class / Weapon / Ability (if allowed).
3. Go to character creation.
4. Pick a Race and Class.
5. Roll (auto) + save the character.
6. View it later on your dashboard.

## 3. Ability Scores
Base scores are generated for:
Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma.

Method:
- For each ability: roll 4 six‑sided dice (4d6), discard the lowest die, sum the top 3.
- After all six are rolled, Race bonuses are added (each bonus is 0, 1, or 2 per ability).
- Final value = Rolled Score + Race Bonus.

No manual editing after save (unless future edit feature is added).

## 4. Races
Each Race stores six bonuses:
- strength_bonus
- dexterity_bonus
- constitution_bonus
- intelligence_bonus
- wisdom_bonus
- charisma_bonus

Allowed values: 0, 1, or 2.  
If a bonus is left blank (or invalid), it counts as 0.

## 5. Classes
Currently store:
- Name
- Description
- Hit Die (e.g. 1d8, 1d10)

(Expansion like proficiencies can be added later.)

## 6. Weapons / Equipment
Fields (simplified):
- Name
- Type (Weapon)
- Damage Dice (e.g. 1d6)
- Damage Type (e.g. slashing)
- (Armor entries may also include AC if added.)

## 7. Abilities / Skills
Simple placeholder entries:
- Name
- Description
- Associated attribute (e.g. Intelligence)

## 8. Adding Game Data (Admin-Style Form)
Select a Type:
- Race → enter name, description, six bonuses (0–2)
- Class → name, description, hit dice
- Ability → name, description, attribute/effect
- Weapon → name, damage, damage type (plus optional AC)

Submit → data is stored → available in character creation.

## 9. Creating a Character (Typical Steps)
1. Open the character creation page.
2. Choose Race (its bonuses will auto-apply after rolling).
3. Choose Class.
4. (If provided) fill any extra required fields.
5. Submit → server rolls stats + applies Race → saves character.

## 10. Example (Race Bonus Application)
- Rolled Dexterity = 14
- Chosen Race has dexterity_bonus = 2
- Final Dexterity = 16 (stored)

## 11. Viewing Characters
Your saved characters list shows:
- Name (if implemented)
- Final ability scores (with bonuses already included)
- Associated Race and Class

## 12. Limits / Current Rules
- No manual reroll button (unless added later).
- No negative racial modifiers.
- No point-buy system (pure random 4d6 method).
- No multiclassing (yet).
- No equipment assignment logic (basic storage only).

## 13. Troubleshooting
| Problem | Cause | Action |
|---------|-------|--------|
| All bonuses show 0 | Race had all zeros or fields missing | Re-add Race with correct values |
| Can’t see new Race | Page cached | Refresh / hard reload |
| Character stats look low | Random variance | Roll another character (future feature if enabled) |
| Weapon not appearing | Not added or form incomplete | Recreate via Add DND Info |

## 14. FAQ
Q: Can I edit a character after creation?  
A: Not in current build.

Q: Are racial bonuses visible separately?  
A: No—only the final totals are stored.

Q: Can I add a bonus above 2?  
A: No—values outside 0–2 are coerced to 0 (or rejected if validation is added).

Q: Are dice rolls shown?  
A: Not yet; only final results are stored.

## 15. Safe Expansion Ideas (Player-Facing)
- Show raw vs modified scores.
- Add roll history modal.
- Add manual stat assignment variant (point buy / standard array).
- Add inventory linking to Equipment entries.

## 16. Glossary
- 4d6 Drop Lowest: Roll four six-sided dice, ignore the smallest, sum the rest.
- Race Bonus: Flat integer added post-roll.
- Hit Die: Die size used for class HP progression (future use).

## 17. Data Integrity Notes
- All ability bonuses default to 0 if not supplied.
- Character scores are immutable post-save (current version).
- Input sanitation handled server-side (basic).

## 18. Player Best Practices
- Plan desired stat focus before choosing Race.
- Add custom Races only if they stay within 0–2 per ability.
- Keep naming consistent (avoid duplicates).

Enjoy building your roster!