import sys
from pathlib import Path
from importlib.machinery import ModuleSpec, SourceFileLoader

# Ensure scripts dir is on sys.path
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


class LiveChatPackageFinder:
    """Enables importing skills.anibon_livechat_analysis.* regardless of hyphenated directory names."""
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if fullname == "skills.anibon_livechat_analysis":
            pkg_dir = Path(__file__).resolve().parent.parent
            spec = ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(pkg_dir)]
            return spec
        elif fullname == "skills.anibon_livechat_analysis.scripts":
            spec = ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(scripts_dir)]
            return spec
        elif fullname.startswith("skills.anibon_livechat_analysis.scripts."):
            mod_name = fullname.split(".")[-1]
            mod_file = scripts_dir / f"{mod_name}.py"
            if mod_file.exists():
                return ModuleSpec(fullname, SourceFileLoader(fullname, str(mod_file)), origin=str(mod_file))
        return None


if not any(isinstance(f, type) and f.__name__ == "LiveChatPackageFinder" for f in sys.meta_path):
    sys.meta_path.insert(0, LiveChatPackageFinder)
