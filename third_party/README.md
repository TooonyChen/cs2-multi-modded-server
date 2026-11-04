# Third-party redistributable sources and notices

The fleet source license does not replace component licenses. The packaged plugins are unmodified upstream binaries, except that configuration and lookup paths are adapted as documented in [BUNDLED-FIXES](../docs/BUNDLED-FIXES.md). Package digests, source commits and source archive digests are in [the baseline manifest](../docs/bundled-baseline.json).

`sources/` accompanies the newly distributed GPL components with the corresponding upstream source and build/project files at the selected revision. CounterStrikeSharp's archive also includes its recursively pinned submodules and their notices; the manifest records those commits. Other archives use `git archive` at the recorded revision. Extract and follow each project's own build instructions; restore its NuGet dependencies at the versions in its project/dependency files. No claim of a reproducible local rebuild is made: these binaries came from official releases/CI, not a local compiler.

| Component | License | Notice/source |
| --- | --- | --- |
| GameModeManager / shared API | MIT | `licenses/GameModeManager-LICENSE`, source archive |
| GG1MapChooser / ggmcAPI | MIT | Plugin-local LICENSE and `licenses/GG1MapChooser-LICENSE`, source archive |
| MenuManagerCore / MenuManagerApi | GPLv3 | Plugin-local LICENSE and `licenses/PanoramaMenuManagerCS2-LICENSE`, source archive; official 1.3.01 core/API bytes match GMM package |
| PMM_GG1MapChooser | GPLv3 | Plugin-local LICENSE and `licenses/PMM-GG1MapChooser-LICENSE`, source archive |
| MultiAddonManager | GPLv3 | `licenses/MultiAddonManager-LICENSE`, source archive; official autoload VDF enabled |
| RetakesAllocator | GPLv3 | `licenses/RetakesAllocator-LICENSE`, official CI source archive |
| CounterStrikeSharp | GPLv3 with upstream linking exception | `licenses/CounterStrikeSharp-LICENSE`, `licenses/CounterStrikeSharp-LICENSE.GPL3`, source archive |
| Gameloop.Vdf | MIT | `licenses/Gameloop.Vdf-LICENSE` |
| Newtonsoft.Json | MIT | `licenses/Newtonsoft.Json-LICENSE` |
| Harmony | MIT | `licenses/Harmony-LICENSE` |

The package dependency manifests (`*.deps.json`) retain the exact dependency names/versions. `licenses/nuget/` retains NuGet license declarations (`.nuspec`) and available package notices plus upstream license texts: Microsoft/FastGenericNew/MySqlConnector/Scrutor/Pomelo are MIT; Dapper/McMaster/Serilog/SQLitePCLRaw are Apache-2.0; Tomlyn is BSD-2-Clause. Microsoft .NET runtime license/third-party notices remain under the existing dotnet trees. Source archives retain each project's dependency declarations and upstream notices. The Workshop addon is downloaded by Steam/MultiAddonManager at runtime and is not redistributed here. Existing Metamod, MultiAddonManager, MatchZy and InventorySimulator artifacts remain unchanged by this upgrade.

FixRandomSpawn is deliberately absent because upstream v1.2.0 does not expose a redistribution license. See the blocker in BUNDLED-FIXES; source availability is not a license grant.
