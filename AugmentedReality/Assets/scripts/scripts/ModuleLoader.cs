using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;

public interface IRigModule
{
	// Called once per Mouse_move agent, from Mouse_move.Initialize().
	void Install(Mouse_move agent);
}

public static class ModuleLoader
{
	static List<IRigModule> modules;

	public static void InstallAll(Mouse_move agent)
	{
		if (modules == null) modules = Load(ModulesDir());
		foreach (var module in modules)
		{
			try
			{
				module.Install(agent);
				Debug.Log($"ModuleLoader: installed {module.GetType().FullName}");
			}
			catch (Exception e)
			{
				Debug.LogError($"ModuleLoader: {module.GetType().FullName}.Install failed");
				Debug.LogException(e);
			}
		}
	}

	static string ModulesDir()
	{
		var args = Environment.GetCommandLineArgs();
		for (int i = 0; i < args.Length - 1; i++)
		{
			if (args[i] == "-modules") return args[i + 1];
		}
		// Application.dataPath is <build>/<name>_Data in a player and <project>/Assets in the editor.
		return Path.Combine(Path.GetDirectoryName(Application.dataPath), "Modules");
	}

	static List<IRigModule> Load(string dir)
	{
		var found = new List<IRigModule>();
		if (!Directory.Exists(dir)) return found;
		foreach (var path in Directory.GetFiles(dir, "*.dll").OrderBy(p => p, StringComparer.Ordinal))
		{
			Type[] types;
			try
			{
				types = Assembly.LoadFrom(path).GetTypes();
			}
			catch (Exception e)
			{
				Debug.LogError($"ModuleLoader: cannot load {path}");
				Debug.LogException(e);
				continue;
			}
			foreach (var type in types.OrderBy(t => t.FullName, StringComparer.Ordinal))
			{
				if (!type.IsPublic || type.IsAbstract || !typeof(IRigModule).IsAssignableFrom(type)) continue;
				try
				{
					found.Add((IRigModule)Activator.CreateInstance(type));
					Debug.Log($"ModuleLoader: loaded {type.FullName} from {path}");
				}
				catch (Exception e)
				{
					Debug.LogError($"ModuleLoader: cannot create {type.FullName}");
					Debug.LogException(e);
				}
			}
		}
		return found;
	}
}
