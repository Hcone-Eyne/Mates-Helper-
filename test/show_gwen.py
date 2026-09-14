"""
Show Gwen's real reasoning from a local Ollama model.

Run:
    python test/show_gwen.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ollama.client import OllamaClient
from agent.gwen.gwen import Gwen, OllamaCriticBackend
from agent.julie.julie import JulieResult
from agent.selina.selina import SelinaResult


def main():
    client = OllamaClient(model="qwen2.5:3b-instruct")
    backend = OllamaCriticBackend(client)
    gwen = Gwen(backend)

    julie_result = JulieResult(
        user_request=(
            "How's my Downloads folder looking? "
            "I think I have to organise it, can you do that?"
        ),
        context=None,
        expanded_task=(
            "Inspect and organize the Downloads folder "
            "by categorizing files into appropriate subfolders."
        ),
        plan=[
            "List all files in the Downloads folder",
            "Categorize files by type",
            "Create category subfolders",
            "Move files into their respective folders",
        ],
        uncertainty=[
            "The user has not specified a preferred folder structure",
            "Some files may be important",
            "Unknown file types may need manual review",
        ],
        raw_response="{}",
    )

    selina_result = SelinaResult(
        success=True,
        expanded_task=(
            "Inspect and organize the Downloads folder "
            "by categorizing files into appropriate subfolders."
        ),
        interpretation=(
            "Task: Inspect and organize Downloads. "
            "Steps: List files; categorize files; "
            "create folders; move files."
        ),
        action="list_all_files_in_the_downloads_folder",
        result={
            "files": [
                "report.pdf",
                "photo.jpg",
                "video.mp4",
                "archive.zip",
                "notes.txt",
            ]
        },
        error=None,
    )

    result = gwen.review_structured(
        julie_result.user_request,
        julie_result,
        selina_result,
    )

    print("\n" + "=" * 60)
    print("GWEN — REAL OLLAMA REVIEW")
    print("=" * 60)

    print("\nAPPROVED:")
    print(result.approved)

    print("\nREASONING:")
    print(result.reasoning)

    print("\nCRITIQUE:")
    print(result.critique)

    print("\nISSUES:")
    if result.issues:
        for issue in result.issues:
            print(f"  - {issue}")
    else:
        print("  None")

    print("\nSAFETY CONCERNS:")
    if result.safety_concerns:
        for concern in result.safety_concerns:
            print(f"  - {concern}")
    else:
        print("  None")

    print("\nRECOMMENDATIONS:")
    if result.recommendations:
        for recommendation in result.recommendations:
            print(f"  - {recommendation}")
    else:
        print("  None")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()