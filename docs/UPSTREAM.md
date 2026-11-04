# Upstream attribution and bundled mod inventory

This project derives from [Kus’ CS2 Modded Dedicated Server](https://github.com/kus/cs2-modded-server). Copyright and license notices in the source and bundled resources are retained. The project source is licensed under [LGPL-3.0](../LICENSE); bundled third-party components retain their own licenses and notices in `game/csgo`. Original contributors remain credited in Git history.

The original single-server deployment instructions are available in [upstream](https://github.com/kus/cs2-modded-server/blob/master/README.md) and this repository’s history. Use this project’s root README for deployment. This inventory records the bundled defaults, not private overlays or proof of plugin compatibility with the latest game. Maintainers update the table alongside reviewed resource changes.

Bundled resources are mounted from the host by the updater, not baked into the runtime image. Bundled does not mean loaded: plugins under `plugins/disabled/` are available for explicit mode/settings loading; startup cfgs and framework configuration determine activation. This public inventory does not include private production replacements or custom menu configurations.

The reviewed baseline, CI pins, package hashes, licenses and migration limits are recorded in [BUNDLED-FIXES.md](BUNDLED-FIXES.md) and [bundled-baseline.json](bundled-baseline.json). The generic resource updater skips these pinned components until a maintainer reviews their replacement.

## Mods installed

Mod | Version | Why
--- | --- | ---
[Metamod:Source](https://www.metamodsource.net/downloads.php?branch=dev) | `2.0.0-1483` | Sits between the Game and the Engine, and allows plugins to intercept calls that flow between
[CounterStrikeSharp](https://github.com/roflmuffin/CounterStrikeSharp) | `1.0.380-1` | Attempts to implement a .NET Core scripting layer on top of a Metamod Source Plugin, allowing developers to create plugins that interact with the game server in a modern language (C#)
[MultiAddonManager](https://github.com/Source2ZE/MultiAddonManager) | `1.7.3` | Allows you to use multiple workshop addons at once and have clients download them [How?](https://github.com/kus/cs2-modded-server#i-want-to-permanently-enable-multi-addon-manager)
[ServerListPlayersFix](https://github.com/Source2ZE/ServerListPlayersFix) | `2.1` | Fixes players not showing up in the server browser
[MovementUnlocker](https://github.com/Source2ZE/MovementUnlocker) | `2.0.1` | Removes max speed limitation from players on the ground, feels like CS:S [How?](https://github.com/kus/cs2-modded-server#i-run-a-surfkzbhop-server-and-want-movementunlocker-and-cs2fixes-rampbugfix-permanently-on)
[CS2Fixes-RampbugFix](https://github.com/Interesting-exe/CS2Fixes-RampbugFix) | `5-1` | Minimizes rampbugs (needs to be enabled via `!settings` [How?](https://github.com/kus/cs2-modded-server#i-run-a-surfkzbhop-server-and-want-movementunlocker-and-cs2fixes-rampbugfix-permanently-on))
[CS2_ExecAfter](https://github.com/kus/CS2_ExecAfter) | `1.0.0` | Executes a command after server event (i.e. OnMapStart) or a delay.
[CS2 Remove Map Weapons](https://github.com/kus/CS2-Remove-Map-Weapons) | `1.0.1` | Remove weapons from the map in CS2 as `mp_weapons_allow_map_placed 0` does not work.
[CS2-FixRandomSpawn](https://github.com/qstage/CS2-FixRandomSpawn) | `1.2.0` | Official plugin and global gamedata, placed under `plugins/disabled` because its Linux callbacks enable random spawns across modes. Upstream license metadata unknown; see [provenance and behavior](BUNDLED-FIXES.md).
[GameModeManager](https://github.com/nickj609/GameModeManager) | `2.0.0` | Mode management with the matching Panorama menu stack and Workshop addon 3831211166; see [baseline and migration](BUNDLED-FIXES.md).
[PanoramaMenuManager](https://github.com/RRimmer/PanoramaMenuManagerCS2) | `1.3.01` | MenuManagerCore and shared MenuManagerApi from the GMM 2.0.0 package
[GG1MapChooser](https://github.com/ssypchenko/GG1MapChooser) | `1.8.1` | Map voting and shared ggmcAPI
[PMM_GG1MapChooser](https://github.com/RRimmer/PMM-GG1MapChooser) | `0.1.0` | Panorama vote/nomination bridge
[Inventory Simulator](https://github.com/ianlucas/cs2-css-inventory-simulator) | `3.7.2` | Use any Weapon, Knife, Gloves, Agent, Music Kit, Pin or Graffiti. [How?](https://github.com/kus/cs2-modded-server#skin-changer)
[CS2-PlayerModelChanger](https://github.com/samyycX/CS2-PlayerModelChanger) | `1.8.6` | A lightweighted counterstrikesharp plugin to change player model. [How?](https://github.com/kus/cs2-modded-server#model-changer)
[MatchZy](https://github.com/shobhit-pathak/MatchZy) | `0.9.2` | MatchZy is a plugin for CS2 for running and managing practice/pugs/scrims/matches with easy configuration!
[MapConfigurator](https://github.com/ManifestManah/MapConfigurator) | `1.0.2` | Allows you to quick and easily create unique configuration files for each map on your server.
[K4-DamageInfo](https://github.com/KitsuneLab-Development/K4-DamageInfo) | `2.4.0` | Displays the amount of damage players have inflicted on the victim's HP and Armor, as well as the hit groups they have hit.
[SimpleAdmin](https://github.com/connercsbn/SimpleAdmin/) | `0.1.2` | Adds basic administrator functions
[CS2Rcon](https://github.com/LordFetznschaedl/CS2Rcon) | `1.2.0` | This is a rudimentary implementation of a RCON plugin for CS2 using CounterStrikeSharp as RCON does not work whilst connected to the server
[SharpTimer](https://github.com/Letaryat/poor-sharptimer) | `0.4.0` | SharpTimer is a simple Surf/KZ/Bhop/MG/Deathrun/etc CS2 Timer plugin
[STFixes](https://github.com/rcnoob/STFixes) | `1.0.5` | A CounterStrikeSharp plugin with common fixes and features for SharpTimer servers
[GunGame](https://github.com/ssypchenko/cs2-gungame) | `1.2.4` | GunGame mode on Counter Strike Sharp
[K4-Arenas](https://github.com/KitsuneLab-Development/K4-Arenas) | `2.0.8` | All in one arena plugin, that you can use to have a ladder type gameplay. Support all map, 2v2/3v3/etc [How?](https://github.com/kus/cs2-modded-server#enable-k4-arenas)
[CS2 Retakes](https://github.com/B3none/cs2-retakes) | `3.1.1` | CS2 implementation of retakes. Based on the version for CS:GO by Splewis.
[CS2 Instadefuse](https://github.com/B3none/cs2-instadefuse) | `2.0.0` | Allows a CT to instantly defuse the bomb when nothing can prevent defusal. Written in C# for CounterStrikeSharp.
[CS2 Retakes Allocator](https://github.com/yonilerner/cs2-retakes-allocator) | `2.4.3` | Advanced weapon allocation for B3none/cs2-retakes
[CS2 Whitelist](https://github.com/PhantomYopta/CS2_WhiteList) | `1.0.0`| Restricts access to the server for SteamID members/employees listed in the whitelist. [How?](https://github.com/kus/cs2-modded-server#enable-whitelist-so-only-a-list-of-people-can-play)
[CS2 Executes](https://github.com/zwolof/cs2-executes) | `1.1.1` | CS2 implementation of executes. Based on the version for CS:GO by Splewis.
[CS2 Advertisement](https://github.com/partiusfabaa/cs2-advertisement) | `1.0.8-recompile` | Allows you to show ads in chat/center/panel. [How?](https://github.com/kus/cs2-modded-server#enable-advertisements)
[CS2 Deathmatch](https://github.com/NockyCZ/CS2-Deathmatch) | `1.3.6` | Custom Deathmatch CS2 plugin (Includes custom spawnpoints, multicfg, gun selection, spawn protection, etc)
[OpenPrefirePrac](https://github.com/lengran/OpenPrefirePrac) | `0.1.47` | Multiple prefire practices on competitive maps and support multiplayer practicing simultaneously.
[CS2-CustomVotes](https://github.com/imi-tat0r/CS2-CustomVotes) | `1.1.3` | A plugin for Counter-Strike 2 to create custom votes for settings.
[deathrun-manager](https://github.com/leoskiline/cs2-deathrun-manager) | `0.5.1` | Deathrun Manager for CounterStrikeSharp Framework CS2.
[AnnouncementBroadcaster](https://github.com/lengran/CS2AnnouncementBroadcaster) | `0.5` | Conditional messages, OnCommand, OnPlayerConnect, OnRoundStart, and TimerMsgs.
[jRandomSkills](https://github.com/Juzlus/jRandomSkills) | `1.2.4.b6` | CS2, but every round is a SURPRISE. Inspiration from [NadeKings video](https://www.youtube.com/watch?v=OQQBUFB56Iw).
[CS2FunMatchPlugin](https://github.com/TitaniumLithium/CS2FunMatchPlugin) | `1.1.1` | Random fun mode every round
[RollTheDice](https://github.com/Kandru/cs2-roll-the-dice) | `26.10.12` | Roll the dice to get either a positive or negative effect for the current round.
[CS2-MutualScoringPlayers](https://github.com/qstage/CS2-MutualScoringPlayers) | `1.0.3` | Keeps score of kills between players.
[CS2WarcraftMod](https://github.com/Wngui/CS2WarcraftMod) | `3.3.5` | An open-source Warcraft mod for CS2 featuring a fully-fledged RPG system.
[cs2-advanced-weapon-system](https://github.com/schwarper/cs2-advanced-weapon-system) | `1.11` | An advanced weapon system that gives full control over weapon attributes, dynamic adjustments to weapon behaviour, restrictions and advanced customisation.
[cs2-OneInTheChamber](https://github.com/ShookEagle/cs2-OneInTheChamber) | `1.0.0` | One in the Chamber game mode.
[cs2-quake-sounds](https://github.com/Kandru/cs2-quake-sounds) | `26.08.1` | Quake Sounds on multi kills.
[CS2-WeaponSpeed](https://github.com/akanora/CS2-WeaponSpeed) | `1.3` | Gives players a speed boost when they fire specified weapons.
[SpectatorList-CS2](https://github.com/wiruwiru/SpectatorList-CS2) | `16` | Shows real-time spectators in on-screen display.
[SLAYER_Football](https://github.com/zakriamansoor47/SLAYER_Football) | `1.1` | Football in CS2.
[SLAYER_Revive](https://github.com/zakriamansoor47/SLAYER_Revive) | `1.3.2` | Revive Your Teammates.
[cs2-TeleportKill](https://github.com/rodopoulos1/cs2-TeleportKill) | `1.0.1` |  Instantly teleport to the location of the enemy you kill.

### Updating the mods in this repo

> [!NOTE]
> This is for maintaining bundled resources in a development checkout. Running fleets apply staged overlays through the updater sidecar; follow [operations and recovery](OPERATIONS.md) before changing shared defaults.

Keeping the table above current used to be a manual chore: check every project for a new release, download it, copy the right files into `/game/`, bump the version and commit. That is now scripted in [`/scripts/update/`](../scripts/update/) and needs no AI, it is plain bash.

```bash
./scripts/update/update.sh --dry-run   # what is out of date and exactly what would change, touches nothing
./scripts/update/update.sh             # apply it, one commit per mod in the style "- UPDATED: MatchZy 0.8.14 > 0.8.15"
./scripts/update/update.sh --list      # every mod, its slug and whether it has an update script yet
```

How it works:

- It goes down the table above, one mod at a time, and compares the version in the table with the latest release on GitHub (or the Metamod:Source download page).
- If there is a newer release **and** a script exists for that mod in `/scripts/update/plugins/`, it downloads the release, copies the files into place the same way the manual updates always did, bumps the version in the table and commits. Mods without a script are just listed so you can update them by hand or [write a script](../scripts/update/README.md#adding-a-plugin-script) for them.
- Config files you may have customised (`/game/csgo/cfg/MatchZy/`, `/game/csgo/cfg/gungame/` etc.) are never overwritten. New upstream settings are printed so you can port them by hand.
- It refuses to run on a dirty working tree, checks everything before touching a file, and can be re-run safely. Anything unexpected is flagged with what is wrong.

Requirements: `bash`, `git`, `curl`, `jq`, `unzip`, `tar` and `rsync` (macOS and Linux are fine, including the stock macOS bash). Being logged in with `gh auth login` (or setting `GITHUB_TOKEN`) avoids GitHub's anonymous API rate limit but is optional. See [`/scripts/update/README.md`](../scripts/update/README.md) for the details and how to add a mod.
