using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace CounterStrikeSharp.API;

public static class Bootstrap
{
    // Same expression as CounterStrikeSharp's Bootstrap.Run content root.
    [UnmanagedCallersOnly]
    public static int Run()
    {
        var contentRoot = new FileInfo(Assembly.GetExecutingAssembly().Location).Directory!.Parent!.FullName;
        System.Console.WriteLine("CONTENT_ROOT=" + contentRoot);
        return 0;
    }
}
