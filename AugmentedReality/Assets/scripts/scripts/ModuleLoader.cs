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
			if (args[i] == "-modules") return RequestedModulesDir(args[i + 1]);
		}
		// Application.dataPath is <build>/<name>_Data in a player and <project>/Assets in the editor.
		return Path.Combine(Path.GetDirectoryName(Application.dataPath), "Modules");
	}

	// Most builds have no <build>/Modules, but a -modules folder that is missing is a typo worth seeing.
	static string RequestedModulesDir(string dir)
	{
		if (!Directory.Exists(dir)) Debug.LogWarning($"ModuleLoader: -modules folder {dir} does not exist");
		return dir;
	}

	static List<IRigModule> Load(string dir)
	{
		var found = new List<IRigModule>();
		foreach (var path in ModuleFiles(dir))
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

	// An unreadable folder must not abort agent initialization, so log it and load nothing.
	static List<string> ModuleFiles(string dir)
	{
		if (!Directory.Exists(dir)) return new List<string>();
		try
		{
			return Directory.GetFiles(dir, "*.dll").OrderBy(p => p, StringComparer.Ordinal).ToList();
		}
		catch (Exception e)
		{
			Debug.LogError($"ModuleLoader: cannot list {dir}");
			Debug.LogException(e);
			return new List<string>();
		}
	}
}
