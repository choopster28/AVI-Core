from pathlib import Path

source_path = Path("/mnt/data/Pasted text.txt")
output_path = Path("/mnt/data/build_team_profiles_fixed.py")

text = source_path.read_text(encoding="utf-8")

# Add a compact, spacing-insensitive franchise key helper.
needle = '''def slugify_team_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value.strip(),
    )

    normalized = normalized.strip("_")

    return normalized or "Unknown_Team"
'''
replacement = '''def normalize_franchise_key(
    value: Any,
) -> str:
    """
    Return a compact franchise key that is insensitive to spaces,
    punctuation, apostrophes, and capitalization.

    Example:
        "SmokyValleyWheatWarriors"
        "Smoky Valley Wheat Warriors"

    Both become:
        "smokyvalleywheatwarriors"
    """
    if value is None:
        return ""

    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).casefold(),
    )


def slugify_team_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value.strip(),
    )

    normalized = normalized.strip("_")

    return normalized or "Unknown_Team"
'''
if needle not in text:
    raise RuntimeError("Could not locate slugify_team_name block.")
text = text.replace(needle, replacement, 1)

# Make roster_id validation explicit and strip team-name whitespace.
needle = '''    roster_id = int(
        roster.get("roster_id")
    )

    owner_id = str(
        roster.get("owner_id", "")
    )
'''
replacement = '''    roster_id_raw = roster.get("roster_id")

    if roster_id_raw is None:
        raise RuntimeError(
            f"Sleeper roster is missing roster_id: {roster}"
        )

    try:
        roster_id = int(roster_id_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid Sleeper roster_id: {roster_id_raw!r}"
        ) from exc

    owner_id = str(
        roster.get("owner_id", "")
    ).strip()
'''
if needle not in text:
    raise RuntimeError("Could not locate roster_id block.")
text = text.replace(needle, replacement, 1)

needle = '''    team_name = (
        user_metadata.get("team_name")
        or user.get("display_name")
        or f"Roster {roster_id}"
    )
'''
replacement = '''    team_name = str(
        user_metadata.get("team_name")
        or user.get("display_name")
        or f"Roster {roster_id}"
    ).strip()

    if not team_name:
        team_name = f"Roster {roster_id}"
'''
if needle not in text:
    raise RuntimeError("Could not locate team_name block.")
text = text.replace(needle, replacement, 1)

# Add stable franchise key to Team Identity.
needle = '''        "## Team Identity",
        f"- Team name: {profile.team_name}",
        f"- Roster ID: {profile.roster_id}",
'''
replacement = '''        "## Team Identity",
        f"- Team name: {profile.team_name}",
        (
            "- Franchise key: "
            f"{normalize_franchise_key(profile.team_name)}"
        ),
        f"- Roster ID: {profile.roster_id}",
'''
if needle not in text:
    raise RuntimeError("Could not locate Team Identity render block.")
text = text.replace(needle, replacement, 1)

# Replace build_team_profiles with a safer implementation by editing key sections.
needle = '''    profiles.sort(
        key=lambda profile: (
            profile.roster_id
        )
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_files: list[str] = []

    updated_date = datetime.now(
        UTC
    ).date().isoformat()

    for profile in profiles:
        filename = (
            f"{profile.roster_id:02d}_"
            f"{slugify_team_name(profile.team_name)}"
            ".md"
        )

        output_path = (
            OUTPUT_DIRECTORY
            / filename
        )

        output_path.write_text(
            render_team_profile(
                profile,
                updated_date=updated_date,
            ),
            encoding="utf-8",
        )

        generated_files.append(
            str(output_path)
        )

        print(
            f"Generated: {output_path}"
        )
'''
replacement = '''    profiles.sort(
        key=lambda profile: (
            profile.roster_id
        )
    )

    expected_team_count = int(
        league_structure.team_count
    )

    if len(profiles) != expected_team_count:
        raise RuntimeError(
            "Team-profile generation stopped before writing files: "
            f"expected {expected_team_count} rosters, "
            f"found {len(profiles)}."
        )

    roster_ids = [
        profile.roster_id
        for profile in profiles
    ]

    if len(set(roster_ids)) != len(roster_ids):
        raise RuntimeError(
            "Duplicate roster IDs were found in the current "
            f"Sleeper export: {roster_ids}"
        )

    franchise_keys = [
        normalize_franchise_key(
            profile.team_name
        )
        for profile in profiles
    ]

    if any(
        not key
        for key in franchise_keys
    ):
        raise RuntimeError(
            "At least one team produced an empty franchise key."
        )

    if len(set(franchise_keys)) != len(franchise_keys):
        raise RuntimeError(
            "Duplicate normalized franchise names were found: "
            f"{franchise_keys}"
        )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    updated_date = datetime.now(
        UTC
    ).date().isoformat()

    expected_outputs: dict[
        Path,
        str,
    ] = {}

    for profile in profiles:
        filename = (
            f"{profile.roster_id:02d}_"
            f"{slugify_team_name(profile.team_name)}"
            ".md"
        )

        output_path = (
            OUTPUT_DIRECTORY
            / filename
        )

        if output_path in expected_outputs:
            raise RuntimeError(
                f"Duplicate team-profile output path: {output_path}"
            )

        expected_outputs[output_path] = (
            render_team_profile(
                profile,
                updated_date=updated_date,
            )
        )

    # Remove stale generated team files left behind by a franchise rename.
    # This prevents downstream workflows from finding 17+ profile files.
    expected_paths = set(
        expected_outputs
    )

    for stale_path in OUTPUT_DIRECTORY.glob(
        "[0-9][0-9]_*.md"
    ):
        if stale_path not in expected_paths:
            stale_path.unlink()
            print(
                f"Removed stale profile: {stale_path}"
            )

    generated_files: list[str] = []

    for output_path, rendered_profile in expected_outputs.items():
        temporary_path = output_path.with_suffix(
            output_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            rendered_profile,
            encoding="utf-8",
        )

        temporary_path.replace(
            output_path
        )

        generated_files.append(
            str(output_path)
        )

        print(
            f"Generated: {output_path}"
        )
'''
if needle not in text:
    raise RuntimeError("Could not locate profile output block.")
text = text.replace(needle, replacement, 1)

# Simplify manifest status now that incorrect team counts fail before writing.
needle = '''        "status": (
            "passed"
            if len(profiles)
            == league_structure.team_count
            else "failed"
        ),
'''
replacement = '''        "status": "passed",
'''
if needle not in text:
    raise RuntimeError("Could not locate manifest status block.")
text = text.replace(needle, replacement, 1)

# Add a main guard so running the script actually generates profiles.
if 'if __name__ == "__main__":' not in text:
    text = text.rstrip() + '''


if __name__ == "__main__":
    build_team_profiles()
'''

output_path.write_text(text, encoding="utf-8")
print(f"Created {output_path}")
