"""SFX Forge MCP server: free, offline procedural sound effects for the game.

Tools
  list_presets()                         -> available sounds with descriptions
  generate(preset, out_path, seed=None)  -> writes a 16-bit WAV
  generate_all(out_dir)                  -> writes every preset as <name>.wav

Registered in the project's .mcp.json as "sfx-forge". Run directly for a CLI build:
  python server.py --all <out_dir>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve(path):
    if path.startswith("res://"):
        path = os.path.join(PROJECT, path[len("res://"):])
    return os.path.abspath(path)


def generate(preset: str, out_path: str, seed: int | None = None) -> str:
    """Render one preset to a WAV file (res:// paths resolve into the Godot project)."""
    if preset not in synth.PRESETS:
        return f"Unknown preset '{preset}'. Use list_presets."
    path = _resolve(out_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = synth.render(preset, seed)
    with open(path, "wb") as fh:
        fh.write(data)
    return f"Wrote {path} ({len(data) // 1024} KiB)"


def generate_all(out_dir: str) -> str:
    """Render every preset into out_dir as <preset>.wav."""
    lines = [generate(name, os.path.join(_resolve(out_dir), name + ".wav")) for name in synth.PRESETS]
    return "\n".join(lines)


def list_presets() -> str:
    """List available sound presets."""
    return "\n".join(f"{name}: {desc}" for name, (_, desc) in synth.PRESETS.items())


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--all":
    print(generate_all(sys.argv[2]))
elif __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("sfx-forge")
    mcp.tool()(list_presets)
    mcp.tool()(generate)
    mcp.tool()(generate_all)
    mcp.run()
