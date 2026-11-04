// Engine boundaries only. The runner compiles ServerManager, RotationManager and
// TimeLimitManager unchanged from the pinned source archives, plus GG1's actual
// next-map command, DoMapChange and ChangeMapInFive methods.
using System.Text.Json;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Timers;
using GameModeManager;
using GameModeManager.Core;
using GameModeManager.CrossCutting;
using GameModeManager.Shared.Models;
using Microsoft.Extensions.Logging;
using Timer = CounterStrikeSharp.API.Modules.Timers.Timer;

class Program {
    static void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
    static void Main(string[] args) {
        var css = args[0] + "/game/csgo/addons/counterstrikesharp/configs/plugins/";
        var json = File.ReadAllText(css + "GameModeManager/GameModeManager.json");
        var config = JsonSerializer.Deserialize<Config>(json)!;
        var ggConfig = JsonSerializer.Deserialize<GGConfig>(File.ReadAllText(css + "GG1MapChooser/GG1MapChooser.json"))!;
        Check(!ggConfig.VoteSettings.ChangeMapAfterVote && !ggConfig.WinDrawSettings.ChangeMapAfterWinDraw && !ggConfig.TimeLimitSettings.ChangeMapAfterTimeLimit, "GG1 must not race the bundled match-end owner");
        foreach (var trigger in new[] {"round", "time"}) {
            var (manager, rotation, time, state, gg) = Setup(config, ggConfig);
            gg.FinishVote("de_inferno"); // actual DoMapChange(MapEnd), as GG1 vote completion calls it
            Check(!Server.Commands.Any(c => c.StartsWith("changelevel")), "end-map vote changed immediately");
            if (trigger == "round") rotation.EventCsWinPanelMatchHandler(new(), new());
            else { time.EnableTimeLimit(1); Timer.Advance(1); }
            Timer.Advance(20);
            Check(Server.Commands.Count(c => c == "changelevel de_inferno") == 1, trigger + ": voted winner did not advance exactly once");
            Check(!Server.Commands.Any(c => c.StartsWith("exec ")), "map advancement unexpectedly changed mode");
            Console.WriteLine("PASS: " + trigger + " end advances voted winner once without mode change");
        }
        {
            var (manager, rotation, time, state, gg) = Setup(config, ggConfig);
            gg.IsVoteInProgress = true;
            rotation.EventCsWinPanelMatchHandler(new(), new());
            time.EnableTimeLimit(1); Timer.Advance(6);
            Check(!Server.Commands.Contains("ggmc_change_nextmap"), "rotation must wait for active vote");
            gg.FinishVote("de_nuke"); Timer.Advance(15);
            Check(Server.Commands.Count(c => c == "changelevel de_nuke") == 1, "concurrent end triggers duplicated/lost vote winner");
            Console.WriteLine("PASS: active vote waits, overlapping round/time triggers produce one change");
        }
        config.Rotation.Enabled = false;
        {
            var (manager, rotation, time, state, gg) = Setup(config, ggConfig);
            gg.FinishVote("de_inferno"); rotation.EventCsWinPanelMatchHandler(new(), new());
            time.EnableTimeLimit(1); Timer.Advance(20);
            Check(!Server.Commands.Any(c => c.StartsWith("changelevel")), "intentional disabled rotation was ignored");
            manager.ChangeMode(new Mode {Name="Manual", Config="private.cfg", DefaultMap=new Map("de_nuke")});
            Timer.Advance(10);
            Check(Server.Commands.Contains("exec private.cfg") && Server.Commands.Contains("changelevel \"de_nuke\""), "manual mode switch depends on rotation flag");
            Console.WriteLine("PASS: disabled rotation stays disabled; manual mode change still executes cfg and map");
        }
        {
            var (_, _, _, _, gg) = Setup(config, ggConfig);
            gg.ImmediateVote("de_nuke"); Timer.Advance(6);
            Check(Server.Commands.Contains("changelevel de_nuke"), "immediate RTV must work even with automatic owners disabled");
            Console.WriteLine("PASS: immediate RTV changes independently of match-end ownership");
        }
    }
    static (ServerManager, RotationManager, TimeLimitManager, PluginState, GG) Setup(Config config, GGConfig ggConfig) {
        Timer.Reset(); Server.Commands.Clear(); Server.CurrentTime=10;
        var state = new PluginState(); state.Game.MapRotations=4; var gg = new GG { Config=ggConfig }; Server.GG=gg;
        var bridge = new MapChooserBridge { GG=gg };
        var manager = new ServerManager(state, new Log<ServerManager>(), new StringLocalizer(), bridge);
        manager.OnConfigParsed(config);
        var rotation = new RotationManager(manager,state); rotation.OnConfigParsed(config);
        var time = new TimeLimitManager(new GameRules(),manager,state,new MaxRoundsManager(),new Localizer(),new Log<TimeLimitManager>());
        time.OnConfigParsed(config);
        return (manager,rotation,time,state,gg);
    }
}
public partial class GG {
    public GGConfig Config = new(); public bool IsVoteInProgress, MapIsChanging;
    public string? _roundEndMap; public string MapToChange="";
    public Log<GG> Logger = new();
    public void FinishVote(string map) { IsVoteInProgress=false; _roundEndMap=map; DoMapChange(map, SSMC_ChangeMapTime.ChangeMapTime_MapEnd); }
    public void ImmediateVote(string map) { IsVoteInProgress=false; DoMapChange(map); }
    void GGMCDoAutoMapChange() => throw new Exception("unexpected random pick instead of voted winner");
    void ExtendMap() => throw new Exception("extension outside this fixture");
    void PrintToServerCenter(params object[] args) {} void PrintToServerChat(params object[] args) {}
    void AddTimer(float seconds, Action action, TimerFlags flags) => new Timer(seconds,action,flags);
    bool TryGetMapInfo(string name, out MapInfo map) { map=new(); return true; }
}
public enum SSMC_ChangeMapTime { ChangeMapTime_Now, ChangeMapTime_MapEnd }
public class MapInfo { public bool WS; public string MapId=""; }
public class GGConfig { public VoteSettings VoteSettings {get;set;}=new(); public WinDrawSettings WinDrawSettings {get;set;}=new(); public TimeSettings TimeLimitSettings {get;set;}=new(); public OtherSettings OtherSettings {get;set;}=new(); }
public class VoteSettings { public bool ChangeMapAfterVote {get;set;} }
public class WinDrawSettings { public bool ChangeMapAfterWinDraw {get;set;} }
public class TimeSettings { public bool ChangeMapAfterTimeLimit {get;set;} }
public class OtherSettings { public bool TvStopRecord {get;set;} }
namespace CounterStrikeSharp.API {
 public static class Server {
    public static List<string> Commands=new(); public static float CurrentTime; public static GG GG=new();
    public static bool IsMapValid(string name)=>true;
    public static void ExecuteCommand(string command) { Commands.Add(command); if(command=="ggmc_change_nextmap") GG.ChangeNextMapCommand(null,new()); }
    public static void PrintToChatAll(string s) {}
 }
}
namespace CounterStrikeSharp.API.Core {
 public enum HookResult { Continue } public enum HookMode { Pre }
 public class CCSPlayerController {} public class GameEventInfo {}
 public class EventCsWinPanelMatch {} public class EventPlayerDisconnect {} public class EventPlayerConnectFull {} public class EventGameEnd {} public class EventRoundAnnounceMatchStart {}
}
namespace CounterStrikeSharp.API.Modules.Commands { public class CommandInfo {} }
namespace CounterStrikeSharp.API.Modules.Timers {
 [Flags] public enum TimerFlags { REPEAT=1, STOP_ON_MAPCHANGE=2 }
 public class Timer {
    static List<Timer> all=new(); float due, interval; Action action; TimerFlags flags; bool killed;
    public Timer(float seconds, Action callback, TimerFlags flags=0) { interval=seconds;due=Server.CurrentTime+seconds;action=callback;this.flags=flags;all.Add(this); }
    public void Kill()=>killed=true;
    public static void Reset()=>all.Clear();
    public static void Advance(float seconds) { float end=Server.CurrentTime+seconds; int count=0; while(true) { var timer=all.Where(t=>!t.killed && t.due<=end).OrderBy(t=>t.due).FirstOrDefault(); if(timer==null) break; if(++count>1000) throw new Exception("timer loop"); Server.CurrentTime=timer.due; if(timer.flags.HasFlag(TimerFlags.REPEAT)) timer.due+=timer.interval;else timer.killed=true; timer.action(); } Server.CurrentTime=end; }
 }
}
namespace CounterStrikeSharp.API.Modules.Cvars {
 public class ConVar { static float value; public static ConVar Find(string name)=>new(); public T GetPrimitiveValue<T>() => (T)(object)value; public void SetValue(float v)=>value=v; }
}
namespace Microsoft.Extensions.Logging {
 public interface ILogger<T> { void LogInformation(string s, params object[] args); void LogWarning(string s, params object[] args); void LogError(string s, params object[] args); void LogDebug(string s, params object[] args); }
 public class Log<T>: ILogger<T> { public void LogInformation(string s,params object[] args){} public void LogWarning(string s,params object[] args){} public void LogError(string s,params object[] args){} public void LogDebug(string s,params object[] args){} }
}
namespace Microsoft.Extensions.Localization { public interface IStringLocalizer {} }
public class Localizer:Microsoft.Extensions.Localization.IStringLocalizer {}
namespace GameModeManager.Contracts { public interface IPluginDependency<T,U> {} }
namespace GameModeManager.Shared.Models {
 public interface IMap { string Name {get;} long WorkshopId {get;} }
 public record Map(string Name):IMap { public long WorkshopId=>-1; }
 public interface IMode { string Name {get;} string Config {get;} IMap? DefaultMap {get;} List<IMap> Maps {get;} }
 public class Mode:IMode { public string Name {get;set;}="Fixture"; public string Config {get;set;}="fixture.cfg"; public IMap? DefaultMap {get;set;} public List<IMap> Maps {get;}=new(){new Map("de_dust2")}; }
}
namespace GameModeManager {
 public class Config { public RotationConfig Rotation {get;set;}=new(); public MapsConfig Maps {get;set;}=new(); public WarmupConfig Warmup {get;set;}=new(); public CommandsConfig Commands {get;set;}=new(); }
 public class RotationConfig { public bool Enabled {get;set;} public bool ModeRotation {get;set;} public int ModeInterval {get;set;}=4; public bool ModeSchedules {get;set;} public List<ScheduleEntry> Schedule {get;set;}=new(); public bool WhenServerEmpty {get;set;} public float CustomTimeLimit {get;set;} }
 public class MapsConfig { public int Delay {get;set;}=5; } public class WarmupConfig { public bool PerMap {get;set;} } public class CommandsConfig { public bool TimeLimit {get;set;} }
 public class ScheduleEntry { public string Time {get;set;}="00:00"; public string Mode {get;set;}=""; }
 public class PluginState { public GameState Game=new(); public TimeState TimeLimit=new(); }
 public class GameState { public bool RotationsEnabled,CountdownRunning,WarmupRunning,WarmupScheduled; public int MapRotations; public IMode CurrentMode=new Mode(); public IMap CurrentMap=new Map("de_dust2"); public Dictionary<string,IMode> Modes=new(){["Other"]=new Mode{Name="Other"}}; }
 public class TimeState { public bool CustomLimit,Enabled,Scheduled; public float CustomStartTime,Duration; }
 public class Plugin { public void AddCommandListener(string name,Func<CCSPlayerController?,CommandInfo,HookResult> cb,HookMode mode) {} public void RegisterEventHandler<T>(Func<T,GameEventInfo,HookResult> cb) {} }
}
namespace GameModeManager.Core {
 public class StringLocalizer { public StringLocalizer() {} public StringLocalizer(Microsoft.Extensions.Localization.IStringLocalizer l,string prefix) {} public string Localize(string s,params object[] args)=>s; public string LocalizeWithPrefix(string s,params object[] args)=>s; }
 public class GameRules { public bool WarmupRunning; public float GameStartTime; } public class MaxRoundsManager { public bool UnlimitedRounds; public int RemainingRounds; }
 public partial class MapChooserBridge { public GG GG=new(); public bool Available=>true; public bool? MapChanging()=>GG.MapIsChanging; public bool VoteInProgress()=>GG.IsVoteInProgress; public void ChangeToMap(IMap map)=>Server.ExecuteCommand("ggmap "+map.Name); }
}
namespace GameModeManager.CrossCutting {
 public static class PlayerExtensions { public static void FreezePlayers() {} public static void UnfreezePlayers() {} public static int ValidPlayerCount(bool bots)=>1; }
 public static class ServerExtensions { public static bool IsServerEmpty()=>false; public static bool IsHibernationEnabled()=>false; }
}
namespace GameModeManager.Timers { public class CountdownTimer { public CountdownTimer(int delay,Action cb,string label) { new Timer(delay,cb); } } }
